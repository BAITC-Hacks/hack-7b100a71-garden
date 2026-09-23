"""HTTP contract and identity boundaries used by frontend and jury uploads."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from conftest import employee_upload, make_employee, multipart


def bearer(token):
    return {"Authorization": "Bearer " + token}


def assert_error(response, status):
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert isinstance(error["code"], str) and error["code"]
    assert isinstance(error["message"], str) and error["message"]
    assert "details" in error


def test_public_health_reports_dataset_snapshot(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "ok"
    assert data["as_of_date"] == "2026-10-01"
    assert data["counts"]["employees"] == 2
    assert data["counts"]["history"] == 0


def test_employee_catalog_profile_history_and_missing_records(client):
    for path in ["/employees", "/employees/person-alpha", "/employees/person-alpha/history", "/events", "/events/event-foundations", "/skills", "/role-profiles"]:
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)
        assert "data" in response.json()
    assert_error(client.get("/employees/missing-person"), 404)
    assert_error(client.get("/events/missing-event"), 404)


def test_completion_requires_retry_key(client):
    response = client.post("/activities/event-foundations/complete", json={"employee_id": "person-alpha"})
    assert_error(response, 422)


def test_completion_and_retry_contract(client):
    arguments = {"json": {"employee_id": "person-alpha", "score": 85}, "headers": {"Idempotency-Key": "http-first-step"}}
    first = client.post("/activities/event-foundations/complete", **arguments)
    assert first.status_code == 200, first.text
    data = first.json()["data"]
    assert data["activity"]["status"] == "completed"
    assert data["effective_skills"]["skill-technical"] == 3
    assert data["replayed"] is False
    repeat = client.post("/activities/event-foundations/complete", **arguments)
    assert repeat.status_code == 200
    assert repeat.json()["data"]["replayed"] is True
    assert repeat.json()["data"]["activity"] == data["activity"]


@pytest.mark.parametrize("payload", [
    {"employee_id": "person-alpha", "score": True},
    {"employee_id": "person-alpha", "feedback_rating": 6},
    {"employee_id": "person-alpha", "unexpected": "field"},
])
def test_completion_validates_payload_without_coercing_invalid_input(client, payload):
    response = client.post("/activities/event-foundations/complete", json=payload, headers={"Idempotency-Key": "invalid-http-request"})
    assert_error(response, 422)


def test_upload_endpoint_accepts_unseen_employee_only_file(client):
    files = multipart(employee_upload([make_employee("jury-http-person")]))
    validated = client.post("/datasets/validate", files=files)
    assert validated.status_code == 200
    assert validated.json()["data"]["valid"] is True
    assert_error(client.get("/employees/jury-http-person"), 404)
    uploaded = client.post("/datasets/upload", files=files)
    assert uploaded.status_code == 200, uploaded.text
    assert client.get("/employees/jury-http-person").status_code == 200


def test_invalid_upload_validation_returns_errors_without_publishing(client):
    files = {"employees_file": ("employees.json", b"{broken-json", "application/json")}
    response = client.post("/datasets/validate", files=files)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["valid"] is False
    assert data["errors"]
    assert data["errors"][0]["location"]
    assert data["errors"][0]["message"]
    assert_error(client.post("/datasets/upload", files=files), 422)


def test_absent_recommendation_engine_is_explicitly_unavailable(client):
    assert_error(client.get("/employees/person-alpha/recommendations"), 503)


def test_authentication_defaults_to_enabled(repository, settings):
    configured = replace(settings, auth_disabled=False, hr_token="hr-secret", employee_tokens={"alpha-secret": "person-alpha"})
    with TestClient(create_app(settings=configured, repository=repository)) as secure:
        assert secure.get("/health").status_code == 200
        assert_error(secure.get("/employees/person-alpha"), 401)
        assert_error(secure.get("/employees/person-alpha", headers=bearer("invalid-secret")), 401)


def test_employee_token_can_access_only_own_profile_history_and_completion(repository, settings):
    configured = replace(settings, auth_disabled=False, hr_token="hr-secret", employee_tokens={"alpha-secret": "person-alpha"})
    headers = bearer("alpha-secret")
    with TestClient(create_app(settings=configured, repository=repository)) as secure:
        for path in ["/employees/person-alpha", "/employees/person-alpha/history", "/events", "/skills", "/role-profiles"]:
            assert secure.get(path, headers=headers).status_code == 200, path
        for path in ["/employees", "/employees/person-beta", "/employees/person-beta/history", "/employees/person-beta/recommendations", "/hr/analytics"]:
            assert_error(secure.get(path, headers=headers), 403)
        completion = secure.post("/activities/event-foundations/complete", json={"employee_id": "person-beta"}, headers={**headers, "Idempotency-Key": "unauthorized-completion"})
        assert_error(completion, 403)
        own_completion = secure.post("/activities/event-foundations/complete", json={"employee_id": "person-alpha"}, headers={**headers, "Idempotency-Key": "authorized-completion"})
        assert own_completion.status_code == 200, own_completion.text


def test_employee_cannot_validate_or_upload_datasets(repository, settings):
    configured = replace(settings, auth_disabled=False, hr_token="hr-secret", employee_tokens={"alpha-secret": "person-alpha"})
    files = multipart(employee_upload([make_employee("forbidden-new-person")]))
    with TestClient(create_app(settings=configured, repository=repository)) as secure:
        for path in ["/datasets/validate", "/datasets/upload"]:
            assert_error(secure.post(path, files=files, headers=bearer("alpha-secret")), 403)
    assert len(repository.view().get_all_employees()) == 2


def test_hr_can_read_profiles_analytics_and_import(repository, settings):
    configured = replace(settings, auth_disabled=False, hr_token="hr-secret", employee_tokens={"alpha-secret": "person-alpha"})
    with TestClient(create_app(settings=configured, repository=repository)) as secure:
        for path in ["/employees", "/employees/person-alpha", "/employees/person-beta/history", "/hr/analytics"]:
            assert secure.get(path, headers=bearer("hr-secret")).status_code == 200
        uploaded = secure.post("/datasets/upload", files=multipart(employee_upload([make_employee("hr-imported-person")])), headers=bearer("hr-secret"))
        assert uploaded.status_code == 200


def test_spoofed_role_headers_do_not_grant_access(repository, settings):
    configured = replace(settings, auth_disabled=False, hr_token="hr-secret", employee_tokens={"alpha-secret": "person-alpha"})
    with TestClient(create_app(settings=configured, repository=repository)) as secure:
        response = secure.get("/hr/analytics", headers={**bearer("alpha-secret"), "X-Role": "hr", "X-Employee-Id": "person-beta"})
        assert_error(response, 403)


def test_cors_preflight_allows_authorization_and_idempotency_headers(client):
    response = client.options("/activities/event-foundations/complete", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type,idempotency-key"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_hr_returns_only_aggregates_and_null_uncomputed_recommendation_coverage(client):
    response = client.get("/hr/analytics")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["employee_count"] == 2
    assert data["employees_without_next_step"]["count"] is None
    assert data["employees_without_next_step"]["available"] is False
    assert data["activity_participation"]["completed"] == 0
    gaps = {gap["skill_id"]: gap for gap in data["common_skill_gaps"]}
    assert gaps["skill-technical"]["employee_count"] == 2
    assert gaps["skill-technical"]["total_levels_missing"] == 4
    assert "person-alpha" not in response.text
    assert "person-beta" not in response.text


def test_employee_listing_returns_consistent_pagination_metadata(client):
    response = client.get("/employees", params={"limit": 1, "offset": 1})
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["meta"]["total"] == 2
    assert body["meta"]["offset"] == 1
    assert body["meta"]["limit"] == 1
    assert body["meta"]["as_of_date"] == "2026-10-01"
    assert_error(client.get("/employees", params={"limit": 100000}), 422)
