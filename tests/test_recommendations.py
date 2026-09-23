"""Engine integration fails explicitly and never invents recommendation output."""

import asyncio
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.services.activity_service import ActivityService
from backend.recommendation.engine import recommend
from conftest import dataset_payload, make_employee, make_event


def recommendation(employee_id="person-alpha", event_id="event-advanced"):
    # A real full boundary fixture replaces the retired reason/evidence DTO.
    return recommend(
        make_employee(employee_id), dataset_payload()["role_profiles"],
        [make_event(event_id, develops_skills=[{
            "skill_id": "skill-technical", "gain": 1, "max_level": 5,
        }])], [], as_of="2026-10-01",
    )


class RecordingProvider:
    def __init__(self):
        self.calls = []

    def recommend(self, employee_id, view):
        self.calls.append((employee_id, view.version))
        return recommendation(employee_id)


def test_engine_result_is_cached_and_completion_invalidates_cache(repository, settings):
    provider = RecordingProvider()
    with TestClient(create_app(settings=settings, repository=repository, recommendation_provider=provider)) as client:
        first = client.get("/employees/person-alpha/recommendations")
        second = client.get("/employees/person-alpha/recommendations")
        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        assert len(provider.calls) == 1
        ActivityService(repository).complete("event-foundations", "person-alpha", "invalidate-recommendations")
        updated = client.get("/employees/person-alpha/recommendations")
        assert updated.status_code == 200
        assert len(provider.calls) == 2
        assert provider.calls[1][1] > provider.calls[0][1]


def test_hr_coverage_reads_cached_results_without_calling_engine(repository, settings):
    provider = RecordingProvider()
    with TestClient(create_app(settings=settings, repository=repository, recommendation_provider=provider)) as client:
        for _ in range(2):
            initial = client.get("/hr/analytics").json()["data"]["employees_without_next_step"]
            assert initial["available"] is True
            assert initial["count"] is None
            assert initial["evaluated_count"] == 0
            assert initial["pending_count"] == 2
        assert provider.calls == []
        client.get("/employees/person-alpha/recommendations")
        evaluated = client.get("/hr/analytics").json()["data"]["employees_without_next_step"]
        assert evaluated["evaluated_count"] == 1
        assert evaluated["pending_count"] == 1
        assert evaluated["complete"] is False
        assert len(provider.calls) == 1


def test_async_engine_is_supported(repository, settings):
    class AsyncProvider:
        async def recommend(self, employee_id, view):
            await asyncio.sleep(0)
            return recommendation(employee_id)

    with TestClient(create_app(settings=settings, repository=repository, recommendation_provider=AsyncProvider())) as client:
        response = client.get("/employees/person-alpha/recommendations")
    assert response.status_code == 200
    item = response.json()["data"]["recommendations"][0]
    assert item["simulation"]["skill_gaps_before"]
    assert item["evidence"]["target_role"] == "Backend Engineer"


def test_engine_timeout_is_reported_without_caching_a_fabricated_result(repository, settings):
    class SlowProvider:
        async def recommend(self, employee_id, view):
            await asyncio.Event().wait()

    quick_timeout = replace(settings, recommendation_timeout_seconds=0.01)
    with TestClient(create_app(settings=quick_timeout, repository=repository, recommendation_provider=SlowProvider())) as client:
        response = client.get("/employees/person-alpha/recommendations")
        assert response.status_code == 504
        assert response.json()["error"]["code"] == "recommendation_timeout"
        coverage = client.get("/hr/analytics").json()["data"]["employees_without_next_step"]
        assert coverage["evaluated_count"] == 0
        assert coverage["count"] is None


@pytest.mark.parametrize("wrong_result", [
    recommendation(employee_id="person-beta"),
    recommendation(event_id="fabricated-event"),
    {"employee_id": "person-alpha", "recommendations": [{"event_id": "event-advanced", "reason": "Insufficient evidence", "evidence": []}]},
])
def test_invalid_provider_output_returns_502(repository, settings, wrong_result):
    class InvalidProvider:
        def recommend(self, employee_id, view):
            return wrong_result

    with TestClient(create_app(settings=settings, repository=repository, recommendation_provider=InvalidProvider())) as client:
        response = client.get("/employees/person-alpha/recommendations")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "invalid_recommendation_result"
    assert "data" not in response.json()


def test_provider_exception_does_not_expose_internal_secret(repository, settings):
    class BrokenProvider:
        def recommend(self, employee_id, view):
            raise RuntimeError("secret-provider-token-do-not-expose")

    with TestClient(create_app(settings=settings, repository=repository, recommendation_provider=BrokenProvider())) as client:
        response = client.get("/employees/person-alpha/recommendations")
    assert response.status_code == 502
    assert "secret-provider-token" not in response.text
    assert "RuntimeError" not in response.text


def test_data_change_during_generation_rejects_stale_recommendation(repository, settings):
    class MutatingProvider:
        def recommend(self, employee_id, view):
            ActivityService(repository).complete("event-foundations", employee_id, "during-generation")
            return recommendation(employee_id)

    with TestClient(create_app(settings=settings, repository=repository, recommendation_provider=MutatingProvider())) as client:
        response = client.get("/employees/person-alpha/recommendations")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "dataset_changed"
        coverage = client.get("/hr/analytics").json()["data"]["employees_without_next_step"]
        assert coverage["evaluated_count"] == 0


def test_optional_coverage_hook_is_cached_per_snapshot_without_recommending_every_employee(repository, settings):
    class CoverageProvider(RecordingProvider):
        def __init__(self):
            super().__init__()
            self.coverage_calls = []

        def coverage(self, view):
            self.coverage_calls.append(view.version)
            return {"evaluated_count": 2, "without_next_step_count": 1}

    provider = CoverageProvider()
    with TestClient(create_app(settings=settings, repository=repository, recommendation_provider=provider)) as client:
        for _ in range(2):
            response = client.get("/hr/analytics")
            assert response.status_code == 200
            summary = response.json()["data"]["employees_without_next_step"]
            assert summary["count"] == 1
            assert summary["evaluated_count"] == 2
            assert summary["pending_count"] == 0
            assert summary["complete"] is True
        assert len(provider.coverage_calls) == 1
        assert provider.calls == []
        ActivityService(repository).complete("event-foundations", "person-alpha", "invalidate-coverage")
        client.get("/hr/analytics")
        assert len(provider.coverage_calls) == 2
        assert provider.coverage_calls[1] > provider.coverage_calls[0]
        assert provider.calls == []


@pytest.mark.parametrize("invalid_summary", [
    {"evaluated_count": 3, "without_next_step_count": 1},
    {"evaluated_count": 1, "without_next_step_count": 2},
    {"evaluated_count": True, "without_next_step_count": 0},
    {"evaluated_count": 1, "without_next_step_count": -1},
])
def test_invalid_coverage_hook_falls_back_to_cached_recommendations(repository, settings, invalid_summary):
    class InvalidCoverageProvider(RecordingProvider):
        def coverage(self, view):
            return invalid_summary

    provider = InvalidCoverageProvider()
    with TestClient(create_app(settings=settings, repository=repository, recommendation_provider=provider)) as client:
        assert client.get("/employees/person-alpha/recommendations").status_code == 200
        response = client.get("/hr/analytics")
        assert response.status_code == 200
        summary = response.json()["data"]["employees_without_next_step"]
        assert summary["count"] == 0
        assert summary["evaluated_count"] == 1
        assert summary["pending_count"] == 1
        assert summary["complete"] is False
        assert len(provider.calls) == 1


@pytest.mark.parametrize("corruption", [
    "duplicate", "mandatory", "unknown_skill", "wrong_rank", "wrong_count",
    "nonfinite", "missing_evidence", "extra_field",
])
def test_rich_transport_preserves_provider_guardrails(repository, settings, corruption):
    class InvalidProvider:
        def recommend(self, employee_id, view):
            result = recommendation(employee_id)
            item = result["recommendations"][0]
            if corruption == "duplicate":
                from copy import deepcopy
                duplicate = deepcopy(item)
                duplicate["rank"] = 2
                result["recommendations"].append(duplicate)
                result["recommendation_count"] = result["candidate_count"] = 2
            elif corruption == "mandatory":
                # The repository owns this flag; a provider cannot override it.
                item["event_id"] = item["simulation"]["event_id"] = "event-foundations"
            elif corruption == "unknown_skill":
                item["simulation"]["skill_impact"][0]["skill_id"] = "invented-skill"
            elif corruption == "wrong_rank":
                item["rank"] = 2
            elif corruption == "wrong_count":
                result["recommendation_count"] = 3
            elif corruption == "nonfinite":
                item["score"] = float("nan")
            elif corruption == "missing_evidence":
                del item["evidence"]["audience_match"]
            else:
                item["fabricated_field"] = "unvalidated"
            return result

    if corruption == "mandatory":
        from backend.data.repository import DatasetRepository
        from conftest import make_dataset
        repository = DatasetRepository(make_dataset(events=[
            make_event("event-foundations", mandatory=True),
            make_event("event-advanced"),
        ]), state_path=None)
    with TestClient(create_app(settings=settings, repository=repository, recommendation_provider=InvalidProvider())) as client:
        response = client.get("/employees/person-alpha/recommendations")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "invalid_recommendation_result"


def test_authorization_precedes_the_single_recommendation_snapshot(repository, settings, monkeypatch):
    configured = replace(settings, auth_disabled=False, hr_token="hr-test-token",
                         employee_tokens={"employee-test-token": "person-alpha"})
    provider = RecordingProvider()
    original_view = repository.view
    snapshots = []

    def capture_view():
        view = original_view()
        snapshots.append(view)
        return view

    with TestClient(create_app(settings=configured, repository=repository, recommendation_provider=provider)) as client:
        monkeypatch.setattr(repository, "view", capture_view)
        headers = {"Authorization": "Bearer employee-test-token"}
        forbidden = client.get("/employees/person-beta/recommendations", headers=headers)
        assert forbidden.status_code == 403
        assert snapshots == []
        assert provider.calls == []
        allowed = client.get("/employees/person-alpha/recommendations", headers=headers)
        assert allowed.status_code == 200
        assert len(snapshots) == 1
        assert provider.calls == [("person-alpha", snapshots[0].version)]
