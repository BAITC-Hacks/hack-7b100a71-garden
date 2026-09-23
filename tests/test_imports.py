"""Validation is read-only, and publication of imports is all-or-nothing."""

import pytest

from backend.data.validation import DatasetValidationError
from backend.errors import AppError
from backend.services.activity_service import ActivityService
from backend.services.dataset_service import DatasetService
from conftest import dataset_payload, employee_upload, files_from_payload, history_csv, make_employee, make_history


def test_validation_reports_counts_without_publishing_import(repository):
    service = DatasetService(repository)
    version = repository.view().version
    result = service.validate(employee_upload([make_employee("jury-newcomer")]))
    assert result["valid"] is True
    assert result["errors"] == []
    assert repository.view().version == version
    assert len(repository.view().get_all_employees()) == 2


def test_invalid_import_reports_actionable_errors_and_leaves_everything_unchanged(repository):
    service = DatasetService(repository)
    bad = employee_upload([make_employee("jury-newcomer")])
    bad["activity_history.csv"] = history_csv([make_history(employee_id="unrelated-missing-person")])
    version = repository.view().version
    validation = service.validate(bad)
    assert validation["valid"] is False
    assert validation["errors"]
    first_error = validation["errors"][0]
    assert first_error["location"]
    assert first_error["message"]
    with pytest.raises((AppError, DatasetValidationError)):
        service.upload(bad)
    assert len(repository.view().get_all_employees()) == 2
    assert repository.view().get_all_history() == []
    assert repository.view().version == version


def test_multiple_imports_keep_previously_imported_profiles_and_live_completions(repository):
    service = DatasetService(repository)
    service.upload(employee_upload([make_employee("jury-first")]))
    ActivityService(repository).complete("event-foundations", "jury-first", "first-step")
    service.upload(employee_upload([make_employee("jury-second")]))
    service.upload({"activity_history.csv": history_csv([make_history("jury-history", employee_id="jury-second")])})
    view = repository.view()
    assert len(view.get_all_employees()) == 4
    assert view.get_effective_skills("jury-first")["skill-technical"] == 3
    assert view.get_effective_skills("jury-second")["skill-technical"] == 3
    assert len(view.get_all_history()) == 2


def test_duplicate_history_record_import_is_rejected_atomically(repository):
    service = DatasetService(repository)
    files = {"activity_history.csv": history_csv([make_history()])}
    service.upload(files)
    version = repository.view().version
    with pytest.raises((AppError, DatasetValidationError)):
        service.upload(files)
    assert len(repository.view().get_all_history()) == 1
    assert repository.view().version == version


def test_complete_replacement_publishes_new_dataset(repository):
    service = DatasetService(repository)
    replacement = files_from_payload(dataset_payload(employees=[make_employee("replacement-person")]))
    service.upload(replacement, mode="replace")
    assert [employee.employee_id for employee in repository.view().get_all_employees()] == ["replacement-person"]


def test_invalid_csv_cannot_replace_or_destroy_published_dataset(repository):
    service = DatasetService(repository)
    replacement = files_from_payload(dataset_payload(employees=[make_employee("replacement-person")]))
    replacement["activity_history.csv"] = b"not,the,required,headers\n"
    version = repository.view().version
    with pytest.raises((AppError, DatasetValidationError)):
        service.upload(replacement, mode="replace")
    assert len(repository.view().get_all_employees()) == 2
    assert repository.view().version == version
