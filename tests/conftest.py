"""Small, synthetic contracts independent of the supplied employee identifiers."""

import copy
import csv
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.data.repository import DatasetRepository
from backend.data.validation import validate_dataset
from backend.models.domain import Dataset


ROOT = Path(__file__).resolve().parents[1]
META = {"dataset": "Synthetic regression dataset", "version": "1.0", "as_of_date": "2026-10-01"}
HISTORY_FIELDS = ["record_id", "employee_id", "event_id", "date", "due_date", "status", "completion_pct", "score", "feedback_rating", "assigned_by"]


def make_employee(employee_id="person-alpha", level=1, **changes):
    employee = {
        "employee_id": employee_id,
        "full_name": "Тестовый сотрудник",
        "department": "Engineering",
        "role": "Backend Engineer",
        "grade": "Junior",
        "manager_id": None,
        "hire_date": "2025-01-01",
        "tenure_months": 21,
        "work_format": "hybrid",
        "preferred_language": "ru",
        "career_goal": {"target_role": "Backend Engineer", "target_grade": "Middle"},
        "skills": {"skill-technical": level},
        "last_review_date": "2026-05-01",
    }
    employee.update(changes)
    return employee


def make_event(event_id="event-foundations", **changes):
    event = {
        "event_id": event_id,
        "title": "Практикум по разработке",
        "description": "Практическое развитие навыка.",
        "type": "course",
        "format": "self_paced",
        "duration_hours": 2,
        "mandatory": False,
        "target_roles": ["Backend Engineer"],
        "target_grades": ["Junior", "Middle"],
        "develops_skills": [{"skill_id": "skill-technical", "gain": 2, "max_level": 3}],
        "prerequisites": {"skill-technical": 1},
        "upcoming_sessions": [],
    }
    event.update(changes)
    return event


def make_history(record_id="history-alpha", **changes):
    record = {
        "record_id": record_id,
        "employee_id": "person-alpha",
        "event_id": "event-foundations",
        "date": "2026-06-01",
        "due_date": None,
        "status": "completed",
        "completion_pct": 100,
        "score": None,
        "feedback_rating": None,
        "assigned_by": "self",
    }
    record.update(changes)
    return record


def dataset_payload(*, employees=None, events=None, history=None, as_of_date=None):
    meta = dict(META)
    if as_of_date is not None:
        meta["as_of_date"] = as_of_date
    return {
        "meta": meta,
        "proficiency_scale": {str(level): "Level %d" % level for level in range(6)},
        "employees": [make_employee(), make_employee("person-beta")] if employees is None else copy.deepcopy(employees),
        "skills": [
            {"skill_id": "skill-technical", "name": "Development", "type": "hard", "category": "engineering", "description": "Development proficiency."},
            {"skill_id": "skill-dialogue", "name": "Dialogue", "type": "soft", "category": "collaboration", "description": "Communication proficiency."},
        ],
        "role_profiles": [
            {"role": "Backend Engineer", "grade": "Junior", "required_skills": {"skill-technical": 3, "skill-dialogue": 2}, "critical_skills": ["skill-technical"]},
            {"role": "Backend Engineer", "grade": "Middle", "required_skills": {"skill-technical": 4, "skill-dialogue": 3}, "critical_skills": ["skill-technical"]},
        ],
        "events": [
            make_event(),
            make_event("event-advanced", develops_skills=[{"skill_id": "skill-technical", "gain": 1, "max_level": 5}]),
            make_event("event-dialogue", prerequisites={}, develops_skills=[{"skill_id": "skill-dialogue", "gain": 1, "max_level": 5}]),
            make_event("EV_036", type="meetup", format="online", prerequisites={}, upcoming_sessions=["2026-10-10"], develops_skills=[{"skill_id": "skill-dialogue", "gain": 1, "max_level": 5}]),
        ] if events is None else copy.deepcopy(events),
        "history": [] if history is None else copy.deepcopy(history),
    }


def make_dataset(**changes):
    return validate_dataset(Dataset.model_validate(dataset_payload(**changes)))


def history_csv(records, fields=None, quoting=csv.QUOTE_MINIMAL):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields or HISTORY_FIELDS, quoting=quoting)
    writer.writeheader()
    writer.writerows(records)
    return stream.getvalue().encode("utf-8")


def employee_upload(employees):
    return {"employees.json": json.dumps({"meta": META, "employees": employees}, ensure_ascii=False).encode("utf-8")}


def files_from_payload(payload):
    meta = payload["meta"]
    return {
        "employees.json": json.dumps({"meta": meta, "employees": payload["employees"]}, ensure_ascii=False).encode(),
        "skills.json": json.dumps({"meta": meta, "proficiency_scale": payload["proficiency_scale"], "skills": payload["skills"], "role_profiles": payload["role_profiles"]}).encode(),
        "events.json": json.dumps({"meta": meta, "events": payload["events"]}, ensure_ascii=False).encode(),
        "activity_history.csv": history_csv(payload["history"]),
    }


def multipart(files):
    fields = {"employees.json": "employees_file", "skills.json": "skills_file", "events.json": "events_file", "activity_history.csv": "activity_history_file"}
    return {fields[name]: (name, content, "text/csv" if name.endswith(".csv") else "application/json") for name, content in files.items()}


@pytest.fixture
def dataset():
    return make_dataset()


@pytest.fixture
def repository(dataset):
    return DatasetRepository(dataset, state_path=None)


@pytest.fixture
def settings():
    return Settings(data_dir=ROOT / "data" / "career_quest_dataset", runtime_state_path=None, auth_disabled=True)


@pytest.fixture
def client(repository, settings):
    from backend.main import create_app

    with TestClient(create_app(settings=settings, repository=repository)) as test_client:
        yield test_client
