"""The official file schema and imports remain usable with unseen input data."""

import csv
import json

import pytest
from pydantic import ValidationError

from backend.data.loader import load_dataset, parse_upload
from backend.data.validation import DatasetValidationError, merge_dataset, validate_dataset
from backend.models.domain import Dataset
from conftest import ROOT, dataset_payload, employee_upload, files_from_payload, history_csv, make_employee, make_history


def test_official_dataset_loads_without_assuming_particular_employee_ids():
    dataset = load_dataset(ROOT / "data" / "career_quest_dataset")
    assert len(dataset.employees) == 200
    assert len(dataset.skills) == 60
    assert len(dataset.role_profiles) == 32
    assert len(dataset.events) == 40
    assert len(dataset.history) == 2743
    assert str(dataset.meta.as_of_date) == "2026-10-01"


@pytest.mark.parametrize("level", [-1, 6, True, 1.5, "2"])
def test_skill_levels_reject_out_of_range_and_non_integer_values(level):
    files = files_from_payload(dataset_payload(employees=[make_employee(level=level)]))
    with pytest.raises((DatasetValidationError, ValidationError)):
        parse_upload(files)


@pytest.mark.parametrize("change", [
    lambda p: p["employees"].append(dict(p["employees"][0])),
    lambda p: p["employees"][0]["skills"].update({"unknown-skill": 2}),
    lambda p: p["events"][0]["prerequisites"].update({"unknown-skill": 1}),
    lambda p: p["employees"][0].update(manager_id="unknown-manager"),
    lambda p: p["history"].append(make_history(employee_id="unknown-person")),
    lambda p: p["history"].append(make_history(event_id="unknown-event")),
    lambda p: p["employees"][0].update(role="Unknown role"),
])
def test_duplicate_ids_and_broken_references_are_rejected(change):
    payload = dataset_payload()
    change(payload)
    with pytest.raises(DatasetValidationError):
        validate_dataset(Dataset.model_validate(payload))


def test_csv_parses_quoted_unicode_fields_and_reordered_columns(dataset):
    record = make_history(record_id="history, quoted \"строка\"")
    columns = list(reversed(record))
    patch = parse_upload({"activity_history.csv": history_csv([record], fields=columns, quoting=csv.QUOTE_ALL)})
    result = merge_dataset(dataset, patch)
    assert result.history[0].record_id == record["record_id"]
    assert result.history[0].score is None
    assert result.history[0].completion_pct == 100


@pytest.mark.parametrize("content", [
    b"record_id,employee_id\nrow,person-alpha\n",
    b"record_id,record_id,employee_id,event_id,date,due_date,status,completion_pct,score,feedback_rating,assigned_by\n",
    b"record_id,employee_id,event_id,date,due_date,status,completion_pct,score,feedback_rating,assigned_by,surprise\n",
    b"record_id,employee_id,event_id,date,due_date,status,completion_pct,score,feedback_rating,assigned_by\nrow,too,short\n",
])
def test_malformed_csv_reports_validation_failure(content):
    with pytest.raises(DatasetValidationError):
        parse_upload({"activity_history.csv": content})


def test_malformed_json_and_invalid_utf8_report_validation_failure():
    for content in [b"{", b"[]", b"\xff"]:
        with pytest.raises(DatasetValidationError):
            parse_upload({"employees.json": content})


def test_employee_only_and_history_only_imports_are_supported(dataset):
    new_employee = make_employee("jury-person-unseen")
    merged = merge_dataset(dataset, parse_upload(employee_upload([new_employee])))
    assert len(merged.employees) == len(dataset.employees) + 1
    record = make_history(employee_id=new_employee["employee_id"])
    final = merge_dataset(merged, parse_upload({"activity_history.csv": history_csv([record])}))
    assert final.history[0].employee_id == new_employee["employee_id"]
    assert len(dataset.employees) == 2
    assert dataset.history == []


def test_replace_requires_complete_dataset(dataset):
    with pytest.raises(DatasetValidationError):
        merge_dataset(dataset, parse_upload(employee_upload([make_employee("replacement")])), mode="replace")


def test_replace_accepts_all_four_files(dataset):
    payload = dataset_payload(employees=[make_employee("replacement")])
    result = merge_dataset(dataset, parse_upload(files_from_payload(payload)), mode="replace")
    assert [employee.employee_id for employee in result.employees] == ["replacement"]


def test_append_cannot_silently_overwrite_existing_employee(dataset):
    with pytest.raises(DatasetValidationError):
        merge_dataset(dataset, parse_upload(employee_upload([make_employee(level=5)])), mode="append")
