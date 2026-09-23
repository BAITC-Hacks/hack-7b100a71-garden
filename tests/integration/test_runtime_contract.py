"""Runtime clock/order is server-owned; every consumer uses the same replay."""
import hashlib
import json
from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.data.loader import parse_upload
from backend.data.repository import DatasetRepository
from backend.data.validation import DatasetValidationError, merge_dataset, validate_dataset
from backend.errors import AppError
from backend.integrations.engine_inputs import history_for_engine
from backend.models.domain import ActivityRecord
from backend.recommendation.history import calculate_history_signals
from backend.recommendation.skills import reconstruct_effective_skills
from backend.services.activity_service import ActivityService
from conftest import (dataset_payload, history_csv, make_dataset, make_employee,
                      make_event, make_history)


NOW = datetime(2026, 9, 23, 12, 34, 56, 789012, timezone.utc)


def direct_levels(repository):
    view = repository.view()
    return reconstruct_effective_skills(
        view.get_employee("person-alpha").model_dump(mode="json"),
        [event.model_dump(mode="json") for event in view.get_all_events()],
        history_for_engine(view.get_employee_history("person-alpha"),
                           view.get_runtime_completion_ids()),
        as_of=view.as_of_date,
    )["effective_skills"]


def test_actual_recording_timestamp_and_logical_demo_date_are_distinct(repository):
    result = ActivityService(repository, clock=lambda: NOW).complete(
        "event-foundations", "person-alpha", "clock-contract",
    )
    row = repository.view().get_employee_history("person-alpha")[0]
    assert row.completed_at == NOW
    assert row.completed_on == date(2026, 10, 1)
    assert row.runtime_sequence == 1
    assert result["effective_skills"] == direct_levels(repository)
    assert result["effective_skills"]["skill-technical"] == 3
    assert repository.get_employee("person-alpha").last_review_date == date(2026, 5, 1)
    assert repository.get_employee("person-alpha").skills == {"skill-technical": 1}


def test_runtime_history_evidence_labels_logical_recency_without_proxy(repository):
    ActivityService(repository, clock=lambda: NOW).complete(
        "event-foundations", "person-alpha", "history-clock-contract",
    )
    view = repository.view()
    history = history_for_engine(view.get_employee_history("person-alpha"),
                                 view.get_runtime_completion_ids())
    result = calculate_history_signals(
        "person-alpha", view.get_event("event-advanced").model_dump(mode="json"),
        [event.model_dump(mode="json") for event in view.get_all_events()], history,
        as_of=view.as_of_date, include_records=True,
    )
    assert result["record_evidence"][0]["date_basis"] == "runtime_completed_on"
    assert result["record_evidence"][0]["age_days"] == 0
    assert result["record_evidence"][0]["recency"] == 1
    assert result["evidence"]["completion_date_proxy_count"] == 0


@pytest.mark.parametrize("second_instant", [NOW, NOW - timedelta(hours=1)])
def test_persisted_sequence_preserves_actual_operation_order_on_clock_tie_or_rollback(tmp_path, second_instant):
    broad = make_event("broad", prerequisites={}, develops_skills=[
        {"skill_id": "skill-technical", "gain": 1, "max_level": 5}])
    capped = make_event("capped", prerequisites={}, develops_skills=[
        {"skill_id": "skill-technical", "gain": 1, "max_level": 1}])
    records = [make_history("z-first", event_id="broad", status="in_progress", completion_pct=20),
               make_history("a-second", event_id="capped", status="in_progress", completion_pct=20)]
    source = make_dataset(employees=[make_employee(level=0)], events=[broad, capped], history=records)
    repository = DatasetRepository(source, state_path=tmp_path / "state.json")
    times = iter([NOW, second_instant])
    service = ActivityService(repository, clock=lambda: next(times))
    service.complete("broad", "person-alpha", "first")
    service.complete("capped", "person-alpha", "second")
    assert repository.get_effective_skills("person-alpha")["skill-technical"] == 1
    assert direct_levels(repository)["skill-technical"] == 1
    restarted = DatasetRepository(source, state_path=tmp_path / "state.json")
    assert direct_levels(restarted) == direct_levels(repository)
    assert restarted.view().get_runtime_completion_ids() == ("z-first", "a-second")
    assert {row.record_id: row.runtime_sequence for row in restarted.get_all_history()} == {
        "z-first": 1, "a-second": 2,
    }


def test_only_trusted_runtime_completion_can_count_on_review_day():
    employee = make_employee(last_review_date="2026-10-01")
    historical = make_history(date="2026-10-01", completed_on="2026-10-01")
    imported = DatasetRepository(make_dataset(employees=[employee], history=[historical]))
    assert direct_levels(imported)["skill-technical"] == 1
    live = DatasetRepository(make_dataset(employees=[employee]))
    ActivityService(live, clock=lambda: NOW).complete("event-foundations", "person-alpha", "post-review")
    assert direct_levels(live)["skill-technical"] == 3


def test_legacy_runtime_state_restores_without_inventing_timestamp_and_extends_order(tmp_path):
    source = make_dataset()
    path = tmp_path / "legacy.json"
    repository = DatasetRepository(source, state_path=path)
    ActivityService(repository, clock=lambda: NOW).complete("event-foundations", "person-alpha", "old")
    payload = json.loads(path.read_text())
    payload["schema_version"] = 1
    for row in payload["dataset"]["history"]:
        row.pop("completed_at")
        row.pop("runtime_sequence")
    for receipt in payload["receipts"].values():
        receipt["result"]["activity"].pop("completed_at")
        receipt["result"]["activity"].pop("runtime_sequence")
    old_source = source.model_dump(mode="json")
    for row in old_source["history"]:
        row.pop("completed_at", None)
        row.pop("runtime_sequence", None)
    old_fingerprint = hashlib.sha256(json.dumps(
        old_source, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode()).hexdigest()
    assert payload["source_fingerprint"] == old_fingerprint
    path.write_text(json.dumps(payload))
    restarted = DatasetRepository(source, state_path=path)
    old_record = restarted.get_employee_history("person-alpha")[0]
    assert old_record.completed_at is None
    assert old_record.runtime_sequence is None
    assert direct_levels(restarted)["skill-technical"] == 3
    adapted = history_for_engine([old_record], restarted.view().get_runtime_completion_ids())[0]
    assert adapted["completed_at"] == "2026-10-01"
    assert adapted["runtime_sequence"] == 1
    new = ActivityService(restarted, clock=lambda: NOW).complete("event-dialogue", "person-alpha", "new")
    assert new["activity"]["runtime_sequence"] == 2
    assert json.loads(path.read_text())["schema_version"] == 2
    assert DatasetRepository(source, state_path=path).get_effective_skills("person-alpha") == direct_levels(restarted)


@pytest.mark.parametrize("timestamp", ["2026-09-01", "2026-09-01T12:00:00", 1000])
def test_model_requires_exact_timezone_aware_completion_timestamp(timestamp):
    with pytest.raises(ValidationError):
        ActivityRecord.model_validate(make_history(completed_at=timestamp))


def test_model_normalizes_timestamp_offset_to_utc():
    record = ActivityRecord.model_validate(make_history(completed_at="2026-09-01T17:00:00+05:00"))
    assert record.completed_at == datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    assert record.completed_at.utcoffset() == timedelta(0)


def test_invalid_service_clock_is_atomic(repository):
    with pytest.raises(AppError, match="aware timestamp"):
        ActivityService(repository, clock=lambda: NOW.replace(tzinfo=None)).complete(
            "event-foundations", "person-alpha", "bad-clock",
        )
    assert repository.version == 1
    assert repository.get_all_history() == []


def test_csv_exact_completion_timestamp_supported_but_runtime_sequence_rejected(dataset):
    record = make_history(date="2026-04-01", completed_at="2026-09-01T12:00:00Z")
    patch = parse_upload({"activity_history.csv": history_csv([record], fields=list(record))})
    repository = DatasetRepository(merge_dataset(dataset, patch))
    assert repository.get_effective_skills("person-alpha")["skill-technical"] == 3
    forged = make_history(runtime_sequence=1, completed_on="2026-10-01")
    with pytest.raises(DatasetValidationError):
        parse_upload({"activity_history.csv": history_csv([forged], fields=list(forged))})
    with pytest.raises(DatasetValidationError):
        merge_dataset(dataset, {"history": [forged]})


@pytest.mark.parametrize("history", [None, 1, "bad", {}])
def test_invalid_history_section_keeps_structured_validation_error(dataset, history):
    with pytest.raises(DatasetValidationError):
        merge_dataset(dataset, {"history": history})


def test_recurring_session_exact_timestamp_prevents_duplicate_same_day():
    record = make_history(event_id="EV_036", date="2026-09-01",
                          completed_at="2026-10-01T10:00:00Z")
    repository = DatasetRepository(make_dataset(history=[record]))
    with pytest.raises(AppError) as error:
        ActivityService(repository, clock=lambda: NOW).complete("EV_036", "person-alpha", "same-session")
    assert error.value.code == "session_already_completed"
    assert repository.version == 1


@pytest.mark.parametrize("changes", [
    {"completed_at": "2026-04-01T12:00:00Z"},
    {"completed_at": "2026-10-02T12:00:00Z"},
    {"completed_at": "2026-09-01T12:00:00Z", "completed_on": "2026-09-02"},
])
def test_untrusted_imported_timestamps_obey_dataset_chronology(changes):
    with pytest.raises(DatasetValidationError):
        make_dataset(history=[make_history(**changes)])


def target_role_repository(**event_changes):
    employee = make_employee(career_goal={"target_role": "Analyst", "target_grade": "Middle"})
    event = make_event(target_roles=["Analyst"], **event_changes)
    payload = dataset_payload(employees=[employee], events=[event])
    payload["role_profiles"].append({
        "role": "Analyst", "grade": "Middle", "required_skills": {"skill-technical": 4},
        "critical_skills": ["skill-technical"],
    })
    return DatasetRepository(validate_dataset(payload))


def test_explicit_destination_admission_keeps_attained_grade():
    repository = target_role_repository(target_grades=["Junior"])
    result = ActivityService(repository, clock=lambda: NOW).complete("event-foundations", "person-alpha", "transition")
    assert result["effective_skills"]["skill-technical"] == 3
    assert repository.get_employee("person-alpha").grade == "Junior"


@pytest.mark.parametrize("event_changes", [
    {"target_grades": ["Middle"]},
    {"prerequisites": {"skill-technical": 5}},
    {"develops_skills": [{"skill_id": "skill-technical", "gain": 1, "max_level": 1}]},
    {"format": "online", "upcoming_sessions": []},
])
def test_destination_role_cannot_bypass_engine_admission(event_changes):
    repository = target_role_repository(**event_changes)
    with pytest.raises(AppError):
        ActivityService(repository, clock=lambda: NOW).complete("event-foundations", "person-alpha", "blocked")
    assert repository.get_all_history() == []
    assert repository.version == 1
