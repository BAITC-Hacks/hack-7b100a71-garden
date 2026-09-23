"""PostgreSQL contracts use an explicitly supplied URL and disposable schemas.

Set CAREER_QUEST_TEST_DATABASE_URL to run the integration tests. Each test owns
only its generated cq_test_* schema; no application schema is reset or reused.
Codec tests run without a database.
"""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest

from backend.data.loader import load_dataset
from backend.data.repository import DatasetRepository
from backend.errors import AppError
from backend.services.activity_service import ActivityService
from backend.services.dataset_service import DatasetService
from conftest import (
    HISTORY_FIELDS, ROOT, dataset_payload, employee_upload, files_from_payload,
    history_csv, make_dataset, make_employee, make_history,
)


def _ordered_dataset():
    """Identifiers deliberately disagree with source order."""
    return make_dataset(
        employees=[make_employee("person-beta", career_goal=None), make_employee()],
        events=list(reversed(dataset_payload()["events"])),
        history=[
            make_history("z-first", event_id="event-advanced", score=87, feedback_rating=4),
            make_history("a-last", event_id="event-foundations", date="2026-07-01"),
        ],
    )


def _files_from_dataset(dataset):
    payload = dataset.model_dump(mode="json")
    files = files_from_payload({**payload, "history": []})
    files["activity_history.csv"] = history_csv(
        payload["history"], fields=[*HISTORY_FIELDS, "completed_on"])
    return files


@pytest.mark.parametrize("source", ["official", "synthetic"])
def test_relational_codec_round_trip_preserves_content_and_order(source):
    from backend.data.postgres_codec import decode_dataset, encode_dataset

    original = (load_dataset(ROOT / "data" / "career_quest_dataset")
                if source == "official" else _ordered_dataset())
    # SQL tables have no implicit row order. The decoder must use stored positions.
    rows = {table: list(reversed(values))
            for table, values in encode_dataset(original).items()}
    restored = decode_dataset(rows, original.meta)
    assert restored.model_dump(mode="json") == original.model_dump(mode="json")


@pytest.fixture
def postgres_database():
    database_url = os.environ.get("CAREER_QUEST_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set CAREER_QUEST_TEST_DATABASE_URL to run PostgreSQL integration tests")
    psycopg = pytest.importorskip("psycopg")
    from psycopg import sql

    from backend.data.postgres import migrate

    schema = "cq_test_" + uuid4().hex
    try:
        migrate(database_url, schema=schema)
        yield database_url, schema
    finally:
        with psycopg.connect(database_url) as connection:
            connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                sql.Identifier(schema)))


@pytest.fixture
def postgres_repository(postgres_database, tmp_path):
    from backend.data.postgres_repository import PostgresRepository

    directory = tmp_path / "dataset"
    directory.mkdir()
    for filename, content in files_from_payload(dataset_payload()).items():
        (directory / filename).write_bytes(content)
    database_url, schema = postgres_database
    repository = PostgresRepository(database_url, schema=schema)
    repository.initialize(directory)
    return repository, directory


def _reopen(postgres_database, directory: Path):
    from backend.data.postgres_repository import PostgresRepository

    database_url, schema = postgres_database
    repository = PostgresRepository(database_url, schema=schema)
    repository.initialize(directory)
    return repository


@pytest.mark.parametrize("source", ["official", "synthetic"])
def test_postgres_round_trip_and_repeat_initialization(postgres_database, tmp_path, source):
    from backend.data.postgres import migrate

    if source == "official":
        directory = ROOT / "data" / "career_quest_dataset"
        original = load_dataset(directory)
    else:
        directory = tmp_path / "ordered-dataset"
        directory.mkdir()
        original = _ordered_dataset()
        for filename, content in _files_from_dataset(original).items():
            (directory / filename).write_bytes(content)
    first = _reopen(postgres_database, directory)
    assert first.view().export_dataset().model_dump(mode="json") == original.model_dump(mode="json")
    # Reapplying migrations and starting another worker must preserve the snapshot.
    migrate(postgres_database[0], schema=postgres_database[1])
    restarted = _reopen(postgres_database, directory)
    assert restarted.view().export_dataset() == original
    assert restarted.version == first.version == 1


def test_completion_import_and_receipt_survive_reopening(postgres_database, postgres_repository):
    repository, directory = postgres_repository
    before = repository.view()
    completed = ActivityService(repository).complete(
        "event-foundations", "person-alpha", "durable-completion")
    DatasetService(repository).upload(employee_upload([make_employee("new-colleague")]))

    restarted = _reopen(postgres_database, directory)
    assert restarted.version == 3
    assert restarted.get_employee("new-colleague").employee_id == "new-colleague"
    assert restarted.get_effective_skills("person-alpha")["skill-technical"] == 3
    assert before.get_employee_history("person-alpha") == []
    assert before.get_employee("new-colleague") is None
    replay = ActivityService(restarted).complete(
        "event-foundations", "person-alpha", "durable-completion")
    assert replay == {**completed, "replayed": True}
    assert restarted.version == 3
    assert len(repository.get_employee_history("person-alpha")) == 1


def test_initialized_database_starts_without_source_files(postgres_database, postgres_repository, tmp_path):
    repository, _directory = postgres_repository
    DatasetService(repository).upload(employee_upload([make_employee("database-only-colleague")]))
    missing_directory = tmp_path / "source-files-no-longer-present"
    assert not missing_directory.exists()
    restarted = _reopen(postgres_database, missing_directory)
    assert restarted.version == repository.version
    assert restarted.view().export_dataset() == repository.view().export_dataset()


def test_concurrent_workers_keep_both_completions(postgres_database, postgres_repository):
    repository, directory = postgres_repository
    second = _reopen(postgres_database, directory)
    barrier = Barrier(2)

    def complete(worker, event_id):
        barrier.wait(timeout=10)
        return ActivityService(worker).complete(event_id, "person-alpha", event_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(complete, worker, event_id) for worker, event_id in (
            (repository, "event-foundations"), (second, "event-dialogue"))]
        results = [future.result(timeout=30) for future in futures]
    assert sorted(result["version"] for result in results) == [2, 3]
    assert repository.version == second.version == 3
    assert {row.event_id for row in repository.get_employee_history("person-alpha")} == {
        "event-foundations", "event-dialogue"}
    assert second.get_effective_skills("person-alpha") == {
        "skill-technical": 3, "skill-dialogue": 1}


def test_concurrent_duplicate_requests_publish_one_completion(postgres_database, postgres_repository):
    repository, directory = postgres_repository
    second = _reopen(postgres_database, directory)
    barrier = Barrier(2)

    def complete(worker):
        barrier.wait(timeout=10)
        return ActivityService(worker).complete(
            "event-foundations", "person-alpha", "one-request")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(complete, worker) for worker in (repository, second)]
        results = [future.result(timeout=30) for future in futures]
    assert sorted(result["replayed"] for result in results) == [False, True]
    assert results[0]["activity"] == results[1]["activity"]
    assert repository.version == second.version == 2
    assert len(second.get_employee_history("person-alpha")) == 1


def test_replace_clears_progress_and_idempotency_receipts(postgres_database, postgres_repository):
    repository, directory = postgres_repository
    original = ActivityService(repository).complete(
        "event-foundations", "person-alpha", "reusable-after-replace")
    DatasetService(repository).upload(files_from_payload(dataset_payload()), mode="replace")
    restarted = _reopen(postgres_database, directory)
    assert restarted.get_employee_history("person-alpha") == []
    assert restarted.get_effective_skills("person-alpha")["skill-technical"] == 1
    result = ActivityService(restarted).complete(
        "event-foundations", "person-alpha", "reusable-after-replace")
    assert result["replayed"] is False
    assert result["activity"]["record_id"] != original["activity"]["record_id"]
    assert restarted.version == 4


def test_legacy_import_preserves_same_day_completion_order(postgres_database, tmp_path):
    from backend.data.postgres_repository import PostgresRepository

    original = make_dataset(
        employees=[make_employee(last_review_date="2026-10-01")],
        history=[
            make_history("z-first", event_id="event-foundations", status="in_progress", completion_pct=20),
            make_history("a-second", event_id="event-advanced", status="in_progress", completion_pct=10),
        ],
    )
    directory = tmp_path / "legacy-source"
    directory.mkdir()
    for filename, content in _files_from_dataset(original).items():
        (directory / filename).write_bytes(content)
    legacy_path = tmp_path / "runtime-state.json"
    legacy = DatasetRepository(original, state_path=legacy_path)
    ActivityService(legacy).complete("event-foundations", "person-alpha", "first")
    completed = ActivityService(legacy).complete("event-advanced", "person-alpha", "second")
    assert completed["effective_skills"]["skill-technical"] == 4

    database_url, schema = postgres_database
    repository = PostgresRepository(database_url, schema=schema)
    repository.initialize(directory, legacy_state_path=legacy_path)
    assert repository.version == legacy.version == 3
    assert repository.get_effective_skills("person-alpha")["skill-technical"] == 4
    assert repository.view().export_dataset() == legacy.view().export_dataset()
    restarted = _reopen(postgres_database, directory)
    replay = ActivityService(restarted).complete("event-advanced", "person-alpha", "second")
    assert replay == {**completed, "replayed": True}
    assert restarted.get_effective_skills("person-alpha")["skill-technical"] == 4


def test_database_error_rolls_back_entire_import(postgres_database, postgres_repository):
    import psycopg
    from psycopg import sql

    repository, directory = postgres_repository
    completed = ActivityService(repository).complete(
        "event-foundations", "person-alpha", "keep-receipt")
    before = repository.view()
    database_url, schema = postgres_database
    with psycopg.connect(database_url) as connection:
        connection.execute(sql.SQL("""
            CREATE FUNCTION {}.reject_test_employee() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.employee_id = 'rejected-import' THEN
                    RAISE EXCEPTION 'deliberate test constraint failure' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END;
            $$
        """).format(sql.Identifier(schema)))
        connection.execute(sql.SQL("""
            CREATE TRIGGER reject_test_employee BEFORE INSERT ON {}.employees
            FOR EACH ROW EXECUTE FUNCTION {}.reject_test_employee()
        """).format(sql.Identifier(schema), sql.Identifier(schema)))

    with pytest.raises(AppError) as error:
        DatasetService(repository).upload(employee_upload([make_employee("rejected-import")]))
    assert error.value.status_code == 503
    restarted = _reopen(postgres_database, directory)
    assert restarted.version == before.version
    assert restarted.view().export_dataset() == before.export_dataset()
    replay = ActivityService(restarted).complete(
        "event-foundations", "person-alpha", "keep-receipt")
    assert replay == {**completed, "replayed": True}


def test_corrupted_idempotency_receipt_is_rejected(postgres_database, postgres_repository):
    import psycopg
    from psycopg import sql

    repository, _directory = postgres_repository
    ActivityService(repository).complete("event-foundations", "person-alpha", "corrupted-receipt")
    database_url, schema = postgres_database
    with psycopg.connect(database_url) as connection:
        connection.execute(sql.SQL("UPDATE {} SET result = %s::jsonb").format(
            sql.Identifier(schema, "idempotency_receipts")), ("{}",))
    with pytest.raises(AppError) as error:
        ActivityService(repository).complete("event-foundations", "person-alpha", "corrupted-receipt")
    assert error.value.code == "database_state_invalid"
    assert error.value.status_code == 503


def test_unfinished_runtime_completion_is_rejected(postgres_database, postgres_repository):
    import psycopg
    from psycopg import sql

    repository, _directory = postgres_repository
    DatasetService(repository).upload({"activity_history.csv": history_csv([
        make_history("still-learning", status="in_progress", completion_pct=25),
    ])})
    database_url, schema = postgres_database
    with psycopg.connect(database_url) as connection:
        connection.execute(sql.SQL("INSERT INTO {} (record_id, position) VALUES (%s, %s)").format(
            sql.Identifier(schema, "runtime_completions")), ("still-learning", 0))
    with pytest.raises(AppError) as error:
        repository.view()
    assert error.value.code == "database_state_invalid"
    assert error.value.status_code == 503
