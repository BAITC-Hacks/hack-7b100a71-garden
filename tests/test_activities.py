"""Completion is an atomic, persistent and retry-safe business operation."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest

from backend.data.repository import DatasetRepository
from backend.errors import AppError
from backend.services.activity_service import ActivityService
from conftest import make_dataset, make_employee, make_event, make_history


def test_completion_applies_gain_and_cap_without_mutating_assessed_profile(repository):
    result = ActivityService(repository).complete("event-foundations", "person-alpha", "completion-001", score=88, feedback_rating=5)
    assert result["effective_skills"]["skill-technical"] == 3
    assert result["replayed"] is False
    history = repository.view().get_employee_history("person-alpha")
    assert len(history) == 1
    assert history[0].status == "completed"
    assert history[0].completion_pct == 100
    assert history[0].score == 88
    assert history[0].feedback_rating == 5
    assert repository.view().get_employee("person-alpha").skills["skill-technical"] == 1


def test_retry_replays_original_result_and_does_not_increment_version(repository):
    service = ActivityService(repository)
    first = service.complete("event-foundations", "person-alpha", "same-request")
    version = repository.view().version
    retry = service.complete("event-foundations", "person-alpha", "same-request")
    assert retry["replayed"] is True
    assert retry["activity"] == first["activity"]
    assert retry["effective_skills"] == first["effective_skills"]
    assert repository.view().version == version
    assert len(repository.view().get_employee_history("person-alpha")) == 1


def test_idempotency_key_cannot_be_reused_for_changed_payload(repository):
    service = ActivityService(repository)
    service.complete("event-foundations", "person-alpha", "same-request", score=88)
    with pytest.raises(AppError) as error:
        service.complete("event-foundations", "person-alpha", "same-request", score=89)
    assert error.value.status_code == 409
    assert len(repository.view().get_employee_history("person-alpha")) == 1


def test_different_employee_may_use_same_idempotency_key(repository):
    service = ActivityService(repository)
    service.complete("event-foundations", "person-alpha", "client-request-1")
    second = service.complete("event-foundations", "person-beta", "client-request-1")
    assert second["replayed"] is False
    assert len(repository.view().get_all_history()) == 2


def test_second_completion_with_new_key_conflicts(repository):
    service = ActivityService(repository)
    service.complete("event-foundations", "person-alpha", "first")
    with pytest.raises(AppError) as error:
        service.complete("event-foundations", "person-alpha", "second")
    assert error.value.status_code == 409
    assert len(repository.view().get_all_history()) == 1


def test_existing_active_record_is_transitioned_without_duplicating_history():
    record = make_history("active-assignment", status="in_progress", completion_pct=40)
    repository = DatasetRepository(make_dataset(history=[record]))
    ActivityService(repository).complete("event-foundations", "person-alpha", "finish-active", record_id="active-assignment")
    history = repository.view().get_employee_history("person-alpha")
    assert len(history) == 1
    assert history[0].record_id == "active-assignment"
    assert history[0].date == date(2026, 6, 1)
    assert history[0].completed_on == date(2026, 10, 1)
    assert history[0].status == "completed"


def test_old_assignment_completed_today_is_new_progress():
    old = make_history("old-assignment", date="2026-04-01", status="in_progress", completion_pct=20)
    repository = DatasetRepository(make_dataset(history=[old]))
    result = ActivityService(repository).complete("event-foundations", "person-alpha", "finish-old")
    assert result["effective_skills"]["skill-technical"] == 3
    assert repository.view().get_effective_skills("person-alpha")["skill-technical"] == 3


def test_missing_prerequisite_prevents_completion_and_preserves_state():
    repository = DatasetRepository(make_dataset(employees=[make_employee(level=0)]))
    version = repository.view().version
    with pytest.raises(AppError):
        ActivityService(repository).complete("event-foundations", "person-alpha", "unqualified")
    assert repository.view().get_all_history() == []
    assert repository.view().version == version


def test_unknown_event_and_employee_return_not_found(repository):
    service = ActivityService(repository)
    for event_id, employee_id in [("missing-event", "person-alpha"), ("event-foundations", "missing-employee")]:
        with pytest.raises(AppError) as error:
            service.complete(event_id, employee_id, "missing")
        assert error.value.status_code == 404
    assert repository.view().get_all_history() == []


def test_recurring_event_allows_new_session_but_rejects_duplicate_same_day():
    previous_session = make_history("previous-club", event_id="EV_036", date="2026-09-01")
    repository = DatasetRepository(make_dataset(history=[previous_session]))
    service = ActivityService(repository)
    result = service.complete("EV_036", "person-alpha", "new-club-session")
    assert result["effective_skills"]["skill-dialogue"] == 2
    assert service.complete("EV_036", "person-alpha", "new-club-session")["replayed"] is True
    with pytest.raises(AppError) as error:
        service.complete("EV_036", "person-alpha", "duplicate-club-session")
    assert error.value.status_code == 409
    assert len(repository.view().get_all_history()) == 2


def test_mandatory_event_can_complete_existing_assignment_only():
    event = make_event("required-course", mandatory=True, prerequisites={}, develops_skills=[])
    record = make_history(event_id="required-course", status="overdue", completion_pct=20, due_date="2026-09-01", assigned_by="hr")
    repository = DatasetRepository(make_dataset(events=[event], history=[record]))
    service = ActivityService(repository)
    service.complete("required-course", "person-alpha", "finish-required")
    assert repository.view().get_employee_history("person-alpha")[0].status == "completed"
    with pytest.raises(AppError):
        service.complete("required-course", "person-beta", "unassigned-required")


def test_concurrent_identical_requests_write_exactly_one_record(repository):
    service = ActivityService(repository)
    barrier = Barrier(6)

    def complete_once(_):
        barrier.wait(timeout=5)
        return service.complete("event-foundations", "person-alpha", "parallel-retry")

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(complete_once, range(6)))
    assert sum(not result["replayed"] for result in results) == 1
    assert len(repository.view().get_all_history()) == 1
    assert repository.view().get_effective_skills("person-alpha")["skill-technical"] == 3


def test_concurrent_distinct_requests_cannot_double_award_same_event(repository):
    service = ActivityService(repository)
    barrier = Barrier(4)

    def complete_once(index):
        barrier.wait(timeout=5)
        try:
            service.complete("event-foundations", "person-alpha", "parallel-%d" % index)
            return 200
        except AppError as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(complete_once, range(4)))
    assert sorted(statuses) == [200, 409, 409, 409]
    assert len(repository.view().get_all_history()) == 1


def test_same_day_completion_order_survives_record_id_sorting_and_restart(tmp_path):
    broad = make_event("broad-gain", prerequisites={}, develops_skills=[{"skill_id": "skill-technical", "gain": 1, "max_level": 5}])
    capped = make_event("capped-gain", prerequisites={}, develops_skills=[{"skill_id": "skill-technical", "gain": 1, "max_level": 1}])
    records = [
        make_history("record-z-first", event_id="broad-gain", status="in_progress", completion_pct=20),
        make_history("record-a-second", event_id="capped-gain", status="in_progress", completion_pct=20),
    ]
    original = make_dataset(employees=[make_employee(level=0)], events=[broad, capped], history=records)
    path = tmp_path / "ordered-completions.json"
    repository = DatasetRepository(original, state_path=path)
    service = ActivityService(repository)
    first = service.complete("broad-gain", "person-alpha", "first-in-time", record_id="record-z-first")
    second = service.complete("capped-gain", "person-alpha", "second-in-time", record_id="record-a-second")
    assert first["effective_skills"]["skill-technical"] == 1
    assert second["effective_skills"]["skill-technical"] == 1
    restored = DatasetRepository(original, state_path=path)
    assert restored.view().get_effective_skills("person-alpha")["skill-technical"] == 1
    assert len(restored.view().get_all_history()) == 2


def test_mandatory_onboarding_is_not_repeatable_after_completion():
    event = make_event("company-onboarding", type="onboarding", mandatory=True, prerequisites={}, develops_skills=[])
    completed = make_history(event_id="company-onboarding", date="2025-01-15", assigned_by="hr")
    repository = DatasetRepository(make_dataset(events=[event], history=[completed]))
    with pytest.raises(AppError) as error:
        ActivityService(repository).complete("company-onboarding", "person-alpha", "repeat-onboarding")
    assert error.value.status_code == 409
    assert len(repository.view().get_all_history()) == 1


def test_completion_keeps_existing_feedback_when_no_new_rating_is_submitted():
    record = make_history("rated-active", status="in_progress", completion_pct=40, feedback_rating=4)
    repository = DatasetRepository(make_dataset(history=[record]))
    result = ActivityService(repository).complete("event-foundations", "person-alpha", "finish-rated-active")
    assert result["activity"]["feedback_rating"] == 4
    assert repository.view().get_employee_history("person-alpha")[0].feedback_rating == 4
