"""Reads are detached snapshots and progress follows assessment dates."""

from datetime import date

from backend.data.repository import DatasetRepository
from backend.services.activity_service import ActivityService
from backend.services.dataset_service import DatasetService
from conftest import employee_upload, make_dataset, make_employee, make_history


def test_read_models_and_skill_maps_cannot_mutate_repository(repository):
    view = repository.view()
    employee = view.get_employee("person-alpha")
    employee.skills["skill-technical"] = 5
    event = view.get_event("event-foundations")
    event.develops_skills[0].gain = 5
    employees = view.get_all_employees()
    employees.clear()
    levels = view.get_effective_skills("person-alpha")
    levels["skill-technical"] = 5
    assert repository.view().get_employee("person-alpha").skills["skill-technical"] == 1
    assert repository.view().get_event("event-foundations").develops_skills[0].gain == 2
    assert len(repository.view().get_all_employees()) == 2
    assert repository.view().get_effective_skills("person-alpha")["skill-technical"] == 1


def test_captured_view_does_not_change_after_completion(repository):
    before = repository.view()
    ActivityService(repository).complete("event-foundations", "person-alpha", "first-completion")
    after = repository.view()
    assert before.get_employee_history("person-alpha") == []
    assert before.get_effective_skills("person-alpha")["skill-technical"] == 1
    assert len(after.get_employee_history("person-alpha")) == 1
    assert after.get_effective_skills("person-alpha")["skill-technical"] == 3
    assert after.version == before.version + 1


def test_absent_skill_is_zero_and_is_increased_on_completion(repository):
    assert repository.view().get_effective_skills("person-alpha").get("skill-dialogue", 0) == 0
    result = ActivityService(repository).complete("event-dialogue", "person-alpha", "learn-dialogue")
    assert result["effective_skills"]["skill-dialogue"] == 1


def test_only_completions_after_last_review_change_effective_skills():
    history = [
        make_history("before-review", date="2026-04-30", event_id="event-dialogue"),
        make_history("same-day-review", date="2026-05-01", event_id="event-foundations"),
        make_history("after-review", date="2026-05-02", event_id="event-advanced"),
        make_history("unfinished", date="2026-06-01", event_id="EV_036", status="in_progress", completion_pct=40),
    ]
    repository = DatasetRepository(make_dataset(history=history))
    for _ in range(3):
        levels = repository.view().get_effective_skills("person-alpha")
        assert levels["skill-technical"] == 2
        assert levels.get("skill-dialogue", 0) == 0
    assert repository.view().get_employee("person-alpha").skills["skill-technical"] == 1


def test_event_max_level_never_decreases_preexisting_skill():
    repository = DatasetRepository(make_dataset(employees=[make_employee(level=5)], history=[make_history()]))
    assert repository.view().get_effective_skills("person-alpha")["skill-technical"] == 5


def test_new_completion_on_assessment_date_counts_as_new_progress():
    repository = DatasetRepository(make_dataset(employees=[make_employee(last_review_date="2026-10-01")]))
    result = ActivityService(repository).complete("event-foundations", "person-alpha", "live-same-day")
    assert result["effective_skills"]["skill-technical"] == 3
    assert repository.view().get_effective_skills("person-alpha")["skill-technical"] == 3


def test_restart_preserves_completion_import_and_idempotency(tmp_path):
    original = make_dataset()
    path = tmp_path / "state.json"
    first = DatasetRepository(original, state_path=path)
    completed = ActivityService(first).complete("event-foundations", "person-alpha", "persisted-request")
    DatasetService(first).upload(employee_upload([make_employee("jury-person-persistent")]))
    version = first.view().version
    restarted = DatasetRepository(original, state_path=path)
    assert restarted.view().get_employee("jury-person-persistent").employee_id == "jury-person-persistent"
    assert restarted.view().get_effective_skills("person-alpha")["skill-technical"] == 3
    replay = ActivityService(restarted).complete("event-foundations", "person-alpha", "persisted-request")
    assert replay["replayed"] is True
    assert replay["activity"] == completed["activity"]
    assert len(restarted.view().get_employee_history("person-alpha")) == 1
    assert restarted.view().version == version


def test_failed_persistence_does_not_publish_partial_completion(tmp_path, monkeypatch):
    from backend.errors import AppError
    import pytest

    repository = DatasetRepository(make_dataset(), state_path=tmp_path / "state.json")
    version = repository.view().version

    def storage_unavailable(*args, **kwargs):
        raise OSError("simulated storage failure")

    monkeypatch.setattr("backend.data.repository.os.replace", storage_unavailable)
    with pytest.raises(AppError) as error:
        ActivityService(repository).complete("event-foundations", "person-alpha", "must-be-atomic")
    assert error.value.status_code == 503
    assert repository.view().get_all_history() == []
    assert repository.view().version == version
    assert not (tmp_path / "state.json").exists()
    assert list(tmp_path.iterdir()) == []


def test_corrupt_idempotency_receipt_prevents_state_restore(tmp_path):
    import json
    import pytest

    original = make_dataset()
    path = tmp_path / "state.json"
    repository = DatasetRepository(original, state_path=path)
    ActivityService(repository).complete("event-foundations", "person-alpha", "persisted-receipt")
    state = json.loads(path.read_text())
    receipt = next(iter(state["receipts"].values()))
    receipt["result"] = "corrupted saved result"
    path.write_text(json.dumps(state))
    with pytest.raises(ValueError, match="idempotency"):
        DatasetRepository(original, state_path=path)
