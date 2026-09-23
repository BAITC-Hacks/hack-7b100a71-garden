"""Real HTTP → repository → deterministic engine integration regressions.

The official dataset is read only. Mutations use isolated repository copies and
pytest temporary runtime snapshots, never the checked-in dataset documents.
"""

import csv
from datetime import datetime, timezone
from copy import deepcopy
import io
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from backend.config import Settings
from backend.data.loader import load_dataset
from backend.data.repository import DatasetRepository
from backend.main import create_app
from backend.recommendation.engine import recommend


ROOT = Path(__file__).resolve().parents[2]
HISTORY_FIELDS = (
    "record_id", "employee_id", "event_id", "date", "due_date", "status",
    "completion_pct", "score", "feedback_rating", "assigned_by",
)


@pytest.fixture(autouse=True)
def no_live_openai(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture(scope="module")
def official_dataset():
    return load_dataset(ROOT / "data" / "career_quest_dataset")


@pytest.fixture
def official_repository(official_dataset):
    return DatasetRepository(official_dataset, state_path=None)


@pytest.fixture
def integration_settings(tmp_path):
    # If the provider mistakenly reads a hardcoded/local dataset, these tests
    # cannot be satisfied by this nonexistent source directory.
    return Settings(data_dir=tmp_path / "not-a-dataset", runtime_state_path=None,
                    auth_disabled=True)


def engine_result(view, employee_id):
    from backend.integrations.engine_inputs import history_for_engine

    return recommend(
        view.get_employee(employee_id).model_dump(mode="json"),
        [row.model_dump(mode="json") for row in view.get_all_role_profiles()],
        [row.model_dump(mode="json") for row in view.get_all_events()],
        history_for_engine(view.get_employee_history(employee_id),
                           view.get_runtime_completion_ids()),
        as_of=view.as_of_date,
    )


def deterministic_fields(api_result):
    result = deepcopy(api_result)
    result.pop("version", None)
    result.pop("explanation_summary", None)
    result.pop("explanation_meta", None)
    for item in result["recommendations"]:
        item.pop("explanation", None)
    return result


def get_data(client, path, **kwargs):
    response = client.get(path, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def complete(client, employee_id, event_id, key="integration-completion", **kwargs):
    response = client.post(
        "/activities/{}/complete".format(event_id),
        json={"employee_id": employee_id},
        headers={"Idempotency-Key": key, **kwargs.pop("headers", {})},
        **kwargs,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def csv_bytes(records):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=HISTORY_FIELDS)
    writer.writeheader()
    writer.writerows(records)
    return stream.getvalue().encode("utf-8")


def new_employee(dataset, employee_id):
    employee = next(row for row in dataset.employees if row.employee_id == "E0001")
    result = employee.model_dump(mode="json")
    result.update(employee_id=employee_id, manager_id=None)
    return result


def employee_upload(dataset, employee):
    return {"employees_file": (
        "employees.json",
        json.dumps({"meta": dataset.meta.model_dump(mode="json"),
                    "employees": [employee]}, ensure_ascii=False).encode("utf-8"),
        "application/json",
    )}


def replacement_upload(dataset, employee):
    meta = dataset.meta.model_dump(mode="json")
    payloads = {
        "employees_file": ("employees.json", {"meta": meta, "employees": [employee]}),
        "skills_file": ("skills.json", {
            "meta": meta, "proficiency_scale": dataset.proficiency_scale,
            "skills": [row.model_dump(mode="json") for row in dataset.skills],
            "role_profiles": [row.model_dump(mode="json") for row in dataset.role_profiles],
        }),
        "events_file": ("events.json", {
            "meta": meta, "events": [row.model_dump(mode="json") for row in dataset.events],
        }),
    }
    files = {field: (name, json.dumps(payload).encode("utf-8"), "application/json")
             for field, (name, payload) in payloads.items()}
    files["activity_history_file"] = ("activity_history.csv", csv_bytes([]), "text/csv")
    return files


def test_e0001_http_completion_recalculates_exactly_once(official_repository, integration_settings):
    repository = official_repository
    baseline = repository.get_employee("E0001").model_dump(mode="json")
    with TestClient(create_app(settings=integration_settings, repository=repository)) as client:
        profile = get_data(client, "/employees/E0001")
        before = get_data(client, "/employees/E0001/recommendations")
        assert before["recommendations"][0]["event_id"] == "EV_005"
        assert before["recommendations"][0]["rank"] == 1
        assert before["career_readiness"]["current"] == pytest.approx(0.5897435897435898)
        assert profile["effective_skills"]["SK_API_DESIGN"] == 2
        assert profile["effective_skills"]["SK_SYSTEM_DESIGN"] == 1
        # Existing completed history has already raised assessed app security
        # from 0 to 1: an incorrect projected-baseline adapter would apply it twice.
        assert baseline["skills"]["SK_APP_SECURITY"] == 0
        assert before["career_state"]["skills_reconstruction"]["effective_skills"]["SK_APP_SECURITY"] == 1

        wall_before = datetime.now(timezone.utc)
        completion = complete(client, "E0001", "EV_005")
        wall_after = datetime.now(timezone.utc)
        exact = datetime.fromisoformat(completion["activity"]["completed_at"].replace("Z", "+00:00"))
        assert exact.tzinfo is not None
        assert wall_before <= exact <= wall_after
        assert completion["activity"]["completed_on"] == "2026-10-01"
        assert completion["activity"]["runtime_sequence"] > 0
        assert completion["effective_skills"]["SK_API_DESIGN"] == 3
        assert completion["effective_skills"]["SK_SYSTEM_DESIGN"] == 2
        assert completion["replayed"] is False

        after = get_data(client, "/employees/E0001/recommendations")
        profile_after = get_data(client, "/employees/E0001")
        assert after["version"] == before["version"] + 1 == completion["version"]
        assert after["career_readiness"]["current"] == pytest.approx(2 / 3)
        assert [row["event_id"] for row in after["recommendations"]] == ["EV_036"]
        assert after["recommendations"][0]["rank"] == 1
        assert after["recommendations"][0]["score"] == pytest.approx(0.5735220760384466)
        assert after["career_state"]["skills_reconstruction"]["effective_skills"] == profile_after["effective_skills"]
        assert profile_after["employee"] == baseline
        assert deterministic_fields(after) == engine_result(repository.view(), "E0001")

        retry = complete(client, "E0001", "EV_005")
        assert retry == {**completion, "replayed": True}
        assert get_data(client, "/employees/E0001/recommendations") == after
        assert repository.version == after["version"]
        assert len([row for row in repository.get_employee_history("E0001")
                    if row.record_id == completion["activity"]["record_id"]]) == 1
        assert repository.get_employee("E0001").model_dump(mode="json") == baseline


def test_e0004_target_role_recommendation_can_complete(official_repository, integration_settings):
    baseline = official_repository.get_employee("E0004").model_dump(mode="json")
    with TestClient(create_app(settings=integration_settings, repository=official_repository)) as client:
        before = get_data(client, "/employees/E0004/recommendations")
        selected = before["recommendations"][0]
        assert selected["event_id"] == "EV_026"
        assert selected["evidence"]["audience_match"] == "target_role"
        assert selected["evidence"]["attained_grade"] == baseline["grade"] == "Middle"
        completion = complete(client, "E0004", "EV_026", "cross-role")
        after = get_data(client, "/employees/E0004/recommendations")
        assert after["career_readiness"]["current"] == pytest.approx(selected["simulation"]["readiness_after"])
        assert "EV_026" not in [row["event_id"] for row in after["recommendations"]]
        assert completion["effective_skills"] == after["career_state"]["skills_reconstruction"]["effective_skills"]
        assert official_repository.get_employee("E0004").model_dump(mode="json") == baseline


@pytest.mark.parametrize("employee_id,status", [
    ("E0006", "no_next_grade"), ("E0018", "no_eligible_recommendations"),
])
def test_normal_empty_results_are_http_200(official_repository, integration_settings, employee_id, status):
    with TestClient(create_app(settings=integration_settings, repository=official_repository)) as client:
        result = get_data(client, "/employees/{}/recommendations".format(employee_id))
        assert result["status"] == status
        assert result["recommendations"] == []
        assert result["recommendation_count"] == 0
        assert result["explanation_summary"]["text"]
        assert result["blocked_summary"] is not None


def test_target_requirements_satisfied_is_http_200(official_dataset, integration_settings):
    snapshot = official_dataset.model_copy(deep=True)
    employee = next(row for row in snapshot.employees if row.employee_id == "E0001")
    target = next(row for row in snapshot.role_profiles
                  if row.role == employee.career_goal.target_role
                  and row.grade == employee.career_goal.target_grade)
    employee.skills = dict(target.required_skills)
    employee.last_review_date = snapshot.meta.as_of_date
    repository = DatasetRepository(snapshot, state_path=None)
    with TestClient(create_app(settings=integration_settings, repository=repository)) as client:
        result = get_data(client, "/employees/E0001/recommendations")
        assert result["status"] == "target_satisfied"
        assert result["career_readiness"]["current"] == 1.0
        assert result["recommendations"] == []
        assert result["explanation_summary"]["text"]
        assert deterministic_fields(result) == engine_result(repository.view(), "E0001")


@pytest.mark.parametrize("language", ["kk", "ru", "en"])
def test_preferred_language_and_missing_key_fallback(official_dataset, integration_settings, language):
    snapshot = official_dataset.model_copy(deep=True)
    next(row for row in snapshot.employees if row.employee_id == "E0001").preferred_language = language
    repository = DatasetRepository(snapshot, state_path=None)
    with TestClient(create_app(settings=integration_settings, repository=repository)) as client:
        result = get_data(client, "/employees/E0001/recommendations")
        assert result["explanation_meta"]["language"] == language
        assert result["explanation_meta"]["provider_status"] == "missing_api_key"
        assert result["explanation_summary"]["language"] == language
        for item in result["recommendations"]:
            assert item["explanation"]["language"] == language
            assert item["explanation"]["source"] == "deterministic"
            assert item["explanation"]["facts"]
        assert deterministic_fields(result) == engine_result(repository.view(), "E0001")


@pytest.mark.parametrize("employee_id", ["E0001", "E0004", "E0006", "E0018"])
def test_full_engine_structure_scores_and_ranks_survive_http(official_repository, integration_settings, employee_id):
    expected = engine_result(official_repository.view(), employee_id)
    with TestClient(create_app(settings=integration_settings, repository=official_repository)) as client:
        result = get_data(client, "/employees/{}/recommendations".format(employee_id))
    assert deterministic_fields(result) == expected


def test_explicit_absent_provider_is_infrastructure_error(official_repository, integration_settings):
    with TestClient(create_app(settings=integration_settings, repository=official_repository,
                               recommendation_provider=None)) as client:
        response = client.get("/employees/E0006/recommendations")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "recommendation_unavailable"


def test_completed_state_and_retry_survive_restart(official_dataset, integration_settings, tmp_path):
    path = tmp_path / "runtime-state.json"
    repository = DatasetRepository(official_dataset, state_path=path)
    with TestClient(create_app(settings=integration_settings, repository=repository)) as client:
        first = complete(client, "E0001", "EV_005", "restart-proof")
        expected = get_data(client, "/employees/E0001/recommendations")
    assert path.exists()
    restored = DatasetRepository(official_dataset, state_path=path)
    with TestClient(create_app(settings=integration_settings, repository=restored)) as client:
        assert get_data(client, "/employees/E0001/recommendations") == expected
        assert complete(client, "E0001", "EV_005", "restart-proof") == {**first, "replayed": True}
        assert get_data(client, "/employees/E0001")["effective_skills"] == first["effective_skills"]
        assert restored.version == expected["version"]


def test_append_unseen_profile_and_history_use_active_snapshot(official_repository, official_dataset, integration_settings):
    employee_id = "jury-unseen-person-alpha"
    with TestClient(create_app(settings=integration_settings, repository=official_repository)) as client:
        original = get_data(client, "/employees/E0001/recommendations")
        response = client.post("/datasets/upload", files=employee_upload(
            official_dataset, new_employee(official_dataset, employee_id)))
        assert response.status_code == 200, response.text
        first = get_data(client, "/employees/{}/recommendations".format(employee_id))
        assert first["employee_id"] == employee_id
        assert first["version"] == original["version"] + 1
        assert deterministic_fields(first) == engine_result(official_repository.view(), employee_id)
        record = {"record_id": "jury-history-new-id", "employee_id": employee_id,
                  "event_id": "EV_005", "date": "2026-09-29", "due_date": "",
                  "status": "completed", "completion_pct": 100, "score": "",
                  "feedback_rating": 5, "assigned_by": "self"}
        upload = client.post("/datasets/upload", files={"activity_history_file": (
            "activity_history.csv", csv_bytes([record]), "text/csv")})
        assert upload.status_code == 200, upload.text
        after = get_data(client, "/employees/{}/recommendations".format(employee_id))
        assert after["version"] == first["version"] + 1
        assert after["career_readiness"]["current"] > first["career_readiness"]["current"]
        assert "EV_005" not in [row["event_id"] for row in after["recommendations"]]
        assert deterministic_fields(after) == engine_result(official_repository.view(), employee_id)


def test_replace_dataset_replaces_provider_snapshot_and_cache(official_repository, official_dataset, integration_settings):
    employee_id = "jury-complete-replacement"
    with TestClient(create_app(settings=integration_settings, repository=official_repository)) as client:
        old = get_data(client, "/employees/E0001/recommendations")
        response = client.post("/datasets/upload?mode=replace", files=replacement_upload(
            official_dataset, new_employee(official_dataset, employee_id)))
        assert response.status_code == 200, response.text
        assert client.get("/employees/E0001/recommendations").status_code == 404
        result = get_data(client, "/employees/{}/recommendations".format(employee_id))
        assert result["version"] == old["version"] + 1
        assert result["employee_id"] == employee_id
        assert deterministic_fields(result) == engine_result(official_repository.view(), employee_id)
        assert official_repository.view().counts()["employees"] == 1


def test_employee_and_hr_authorization_on_real_provider(official_repository, tmp_path):
    settings = Settings(data_dir=tmp_path / "absent", runtime_state_path=None,
                        hr_token="integration-hr-token",
                        employee_tokens={"integration-employee-token": "E0001"})
    employee_headers = {"Authorization": "Bearer integration-employee-token"}
    hr_headers = {"Authorization": "Bearer integration-hr-token"}
    with TestClient(create_app(settings=settings, repository=official_repository)) as client:
        assert client.get("/employees/E0001/recommendations").status_code == 401
        assert client.get("/employees/E0001/recommendations", headers=employee_headers).status_code == 200
        assert client.get("/employees/E0004/recommendations", headers=employee_headers).status_code == 403
        forbidden = client.post("/activities/EV_026/complete", json={"employee_id": "E0004"},
                                headers={**employee_headers, "Idempotency-Key": "forbidden"})
        assert forbidden.status_code == 403
        assert client.post("/datasets/validate", headers=employee_headers).status_code == 403
        assert client.get("/hr/analytics", headers=employee_headers).status_code == 403
        assert client.get("/employees/E0004/recommendations", headers=hr_headers).status_code == 200
        complete(client, "E0001", "EV_005", "authorized", headers=employee_headers)
        assert client.get("/hr/analytics", headers=hr_headers).status_code == 200


def test_official_backend_projection_equals_engine_for_every_employee(official_repository):
    view = official_repository.view()
    for employee in view.get_all_employees():
        result = engine_result(view, employee.employee_id)
        assert view.get_effective_skills(employee.employee_id) == result["career_state"]["skills_reconstruction"]["effective_skills"]
