"""Validation of relationships and rules within a complete dataset snapshot."""

from collections import defaultdict
from typing import Any, Dict, List, Mapping, Set

from pydantic import ValidationError

from backend.models.domain import GRADES, Dataset


class DatasetValidationError(ValueError):
    """All detectable input issues, safe to return as a structured API response."""

    def __init__(self, issues: List[Dict[str, str]]):
        self.issues = issues
        super().__init__("Dataset validation failed")


def schema_issues(error: ValidationError, location: str) -> List[Dict[str, str]]:
    issues = []
    for item in error.errors(include_url=False, include_context=False, include_input=False):
        suffix = ".".join(str(part) for part in item["loc"])
        issues.append({
            "code": "schema_error",
            "location": ".".join(part for part in (location, suffix) if part),
            "message": item["msg"],
        })
    return issues


def validate_dataset(dataset: Dataset) -> Dataset:
    """Return a validated copy, or report schema and cross-record errors.

    Current assessed skills cannot establish what prerequisites someone met in
    the past. Similarly, current roles are not a reliable historical audience.
    Neither is used to reject historical participation.
    """
    try:
        dataset = Dataset.model_validate(
            dataset.model_dump() if isinstance(dataset, Dataset) else dataset
        )
    except ValidationError as exc:
        raise DatasetValidationError(schema_issues(exc, "dataset")) from exc

    issues: List[Dict[str, str]] = []

    def issue(code: str, location: str, message: str) -> None:
        issues.append({"code": code, "location": location, "message": message})

    def index_unique(rows, key, location):
        result = {}
        for index, row in enumerate(rows):
            identifier = key(row)
            if identifier in result:
                issue("duplicate_id", "{}[{}]".format(location, index),
                      "Duplicate identifier: {}".format(identifier))
            else:
                result[identifier] = row
        return result

    def unique_values(values, location):
        seen = set()
        for value in values:
            if value in seen:
                issue("duplicate_value", location, "Repeated value: {}".format(value))
            seen.add(value)

    def references(values, known, location):
        for value in sorted(set(values) - set(known)):
            issue("unknown_reference", location, "Unknown reference: {}".format(value))

    employees = index_unique(dataset.employees, lambda row: row.employee_id, "employees")
    skills = index_unique(dataset.skills, lambda row: row.skill_id, "skills")
    events = index_unique(dataset.events, lambda row: row.event_id, "events")
    profiles = index_unique(dataset.role_profiles, lambda row: (row.role, row.grade),
                            "role_profiles")
    index_unique(dataset.history, lambda row: row.record_id, "history")
    roles: Set[str] = {profile.role for profile in dataset.role_profiles}
    snapshot = dataset.meta.as_of_date

    if set(dataset.proficiency_scale) != {str(level) for level in range(6)}:
        issue("invalid_proficiency_scale", "proficiency_scale",
              "The scale must describe exactly the levels 0, 1, 2, 3, 4 and 5")

    for index, employee in enumerate(dataset.employees):
        prefix = "employees[{}]({})".format(index, employee.employee_id)
        references(employee.skills, skills, prefix + ".skills")
        if (employee.role, employee.grade) not in profiles:
            issue("unknown_role_profile", prefix + ".role",
                  "No role profile for {} / {}".format(employee.role, employee.grade))
        goal = employee.career_goal
        if goal and (goal.target_role, goal.target_grade) not in profiles:
            issue("unknown_role_profile", prefix + ".career_goal",
                  "No role profile for the career goal {} / {}".format(
                      goal.target_role, goal.target_grade))
        manager = employees.get(employee.manager_id)
        if employee.manager_id is not None:
            if manager is None:
                issue("unknown_reference", prefix + ".manager_id",
                      "Unknown employee: {}".format(employee.manager_id))
            elif manager.employee_id == employee.employee_id:
                issue("invalid_manager", prefix + ".manager_id",
                      "An employee cannot manage themselves")
            elif manager.grade != "Lead" or manager.department != employee.department:
                issue("invalid_manager", prefix + ".manager_id",
                      "The manager must be a Lead in the same department")
        if employee.hire_date > snapshot:
            issue("future_date", prefix + ".hire_date", "Hire date is after the snapshot date")
        if not employee.hire_date <= employee.last_review_date <= snapshot:
            issue("invalid_chronology", prefix + ".last_review_date",
                  "Review date must be between the hire date and the snapshot date")
        months = ((snapshot.year - employee.hire_date.year) * 12
                  + snapshot.month - employee.hire_date.month
                  - (snapshot.day < employee.hire_date.day))
        if employee.tenure_months != months:
            issue("invalid_tenure", prefix + ".tenure_months",
                  "Expected {} full months at the snapshot date".format(months))

    for index, profile in enumerate(dataset.role_profiles):
        prefix = "role_profiles[{}]({}/{})".format(index, profile.role, profile.grade)
        references(profile.required_skills, skills, prefix + ".required_skills")
        references(profile.critical_skills, skills, prefix + ".critical_skills")
        unique_values(profile.critical_skills, prefix + ".critical_skills")
        for skill_id in set(profile.critical_skills) - set(profile.required_skills):
            issue("invalid_critical_skill", prefix + ".critical_skills",
                  "Critical skill {} must have a required level".format(skill_id))
        for earlier_grade in GRADES[:GRADES.index(profile.grade)]:
            earlier = profiles.get((profile.role, earlier_grade))
            if earlier is None:
                continue
            for skill_id, earlier_level in earlier.required_skills.items():
                if profile.required_skills.get(skill_id, 0) < earlier_level:
                    issue("decreasing_requirement", prefix + ".required_skills." + skill_id,
                          "Requirement cannot be lower than for {}".format(earlier_grade))

    for index, event in enumerate(dataset.events):
        prefix = "events[{}]({})".format(index, event.event_id)
        references(event.target_roles, roles, prefix + ".target_roles")
        references(event.prerequisites, skills, prefix + ".prerequisites")
        references([gain.skill_id for gain in event.develops_skills], skills,
                   prefix + ".develops_skills")
        unique_values(event.target_roles, prefix + ".target_roles")
        unique_values(event.target_grades, prefix + ".target_grades")
        unique_values([gain.skill_id for gain in event.develops_skills],
                      prefix + ".develops_skills")
        unique_values(event.upcoming_sessions, prefix + ".upcoming_sessions")
        if not event.target_roles or not event.target_grades:
            issue("empty_audience", prefix, "An event must have target roles and grades")
        if event.format == "self_paced" and event.upcoming_sessions:
            issue("invalid_schedule", prefix + ".upcoming_sessions",
                  "Self-paced events do not have scheduled sessions")
        if any(session < snapshot for session in event.upcoming_sessions):
            issue("past_session", prefix + ".upcoming_sessions",
                  "Upcoming sessions must be on or after the snapshot date")
        if event.type == "compliance" and event.develops_skills:
            issue("invalid_compliance_gains", prefix + ".develops_skills",
                  "Compliance events do not increase assessed skills")

    participation = defaultdict(list)
    runtime_sequences = set()
    for index, record in enumerate(dataset.history):
        prefix = "history[{}]({})".format(index, record.record_id)
        employee = employees.get(record.employee_id)
        event = events.get(record.event_id)
        if employee is None:
            issue("unknown_reference", prefix + ".employee_id",
                  "Unknown employee: {}".format(record.employee_id))
        elif record.date < employee.hire_date:
            issue("invalid_chronology", prefix + ".date", "Participation predates the hire date")
        if event is None:
            issue("unknown_reference", prefix + ".event_id",
                  "Unknown event: {}".format(record.event_id))
        if record.date > snapshot:
            issue("future_date", prefix + ".date", "History date is after the snapshot date")
        if record.due_date is not None and record.due_date < record.date:
            issue("invalid_chronology", prefix + ".due_date",
                  "Due date cannot precede the enrollment or session date")
        if record.completed_on is not None:
            if record.status != "completed":
                issue("invalid_completion_date", prefix + ".completed_on",
                      "Only a completed activity may have a completion date")
            if not record.date <= record.completed_on <= snapshot:
                issue("invalid_chronology", prefix + ".completed_on",
                      "Completion date must be between the history date and the snapshot date")
        if record.runtime_sequence is not None:
            if record.runtime_sequence in runtime_sequences:
                issue("duplicate_runtime_sequence", prefix + ".runtime_sequence",
                      "Runtime sequence must be unique across the snapshot")
            runtime_sequences.add(record.runtime_sequence)
        elif record.completed_at is not None:
            # Imported exact timestamps describe dataset chronology; only
            # trusted runtime context distinguishes recording and logical clocks.
            completion_day = record.completed_at.date()
            if not record.date <= completion_day <= snapshot:
                issue("invalid_chronology", prefix + ".completed_at",
                      "Completion timestamp must be between participation and snapshot dates")
            if record.completed_on is not None and record.completed_on != completion_day:
                issue("invalid_chronology", prefix + ".completed_on",
                      "Imported completion date must match the exact completion timestamp")
        if record.status == "completed" and record.completion_pct != 100:
            issue("invalid_completion", prefix + ".completion_pct",
                  "Completed activities require completion_pct=100")
        if record.status in {"in_progress", "dropped", "overdue"} and record.completion_pct > 95:
            issue("invalid_completion", prefix + ".completion_pct",
                  "{} requires completion_pct at most 95".format(record.status))
        if record.status == "dropped" and record.completion_pct < 5:
            issue("invalid_completion", prefix + ".completion_pct",
                  "Dropped activities require completion_pct of at least 5")
        if record.status in {"no_show", "declined"} and record.completion_pct != 0:
            issue("invalid_completion", prefix + ".completion_pct",
                  "{} requires completion_pct=0".format(record.status))
        if record.status == "declined" and record.assigned_by == "self":
            issue("invalid_assignment", prefix + ".assigned_by",
                  "Declined activities must have been assigned by a manager or HR")
        if record.status == "overdue":
            if record.due_date is None:
                issue("missing_due_date", prefix + ".due_date", "Overdue activities require a due date")
            elif record.due_date >= snapshot:
                issue("invalid_overdue", prefix + ".due_date",
                      "An overdue activity must have a due date before the snapshot date")
        if record.score is not None and record.status != "completed":
            issue("invalid_score", prefix + ".score", "A final score requires a completed activity")
        if event is not None:
            if record.due_date is not None and not event.mandatory:
                issue("invalid_due_date", prefix + ".due_date",
                      "Only mandatory activities have due dates")
            if record.status == "overdue" and not event.mandatory:
                issue("invalid_status", prefix + ".status", "Only mandatory activities can be overdue")
            if record.status == "no_show" and event.format == "self_paced":
                issue("invalid_status", prefix + ".status", "No-show requires a scheduled event")
            if record.score is not None and event.type not in {"course", "certification", "compliance"}:
                issue("invalid_score", prefix + ".score",
                      "Only courses, certifications and compliance activities have scores")
            participation[(record.employee_id, record.event_id)].append((record, prefix))

    for (_employee_id, event_id), records in participation.items():
        event = events[event_id]
        # The published file contains annual compliance repetitions despite the
        # README's blanket no-repeat rule. Onboarding is still a one-time event.
        if event_id == "EV_036" or (event.mandatory and event.type == "compliance"):
            continue
        completed = [(record, prefix) for record, prefix in records if record.status == "completed"]
        if len(completed) > 1:
            issue("repeated_completion", completed[1][1],
                  "This event is already completed for the employee")
        if completed:
            def completion_date(record):
                return (record.completed_on or
                        (record.completed_at.date() if record.completed_at is not None else record.date))
            first = min(completed, key=lambda item: completion_date(item[0]))[0]
            # A historical self-paced date is enrollment, not completion. It
            # cannot establish whether another attempt happened after finishing.
            if first.completed_on is not None or first.completed_at is not None or event.format != "self_paced":
                finished_on = completion_date(first)
                for record, prefix in records:
                    if record.record_id != first.record_id and record.date > finished_on:
                        issue("participation_after_completion", prefix,
                              "This one-time event has participation after an earlier completion")

    if issues:
        raise DatasetValidationError(issues)
    return dataset


def merge_dataset(base: Dataset, patch: Mapping[str, Any], mode: str = "append") -> Dataset:
    """Merge new profiles/history or replace all four official documents.

    No object in the input snapshot or patch is mutated. The caller can commit
    the returned dataset atomically only after validation has succeeded.
    """
    allowed = {"meta", "proficiency_scale", "employees", "skills", "role_profiles", "events", "history"}
    if mode not in {"append", "replace"}:
        raise DatasetValidationError([{
            "code": "invalid_mode", "location": "mode", "message": "Expected append or replace"
        }])
    unknown = set(patch) - allowed
    if unknown:
        raise DatasetValidationError([{
            "code": "unknown_field", "location": str(key), "message": "Unknown dataset section"
        } for key in sorted(unknown)])
    incoming_history = patch.get("history", ())
    for index, row in enumerate(incoming_history if isinstance(incoming_history, (list, tuple)) else ()):
        row = row.model_dump() if hasattr(row, "model_dump") else row
        if isinstance(row, Mapping) and row.get("runtime_sequence") is not None:
            raise DatasetValidationError([{
                "code": "server_owned_field", "location": "history[{}].runtime_sequence".format(index),
                "message": "Runtime order can only be assigned by the completion service",
            }])
    if mode == "replace":
        missing = allowed - set(patch)
        if missing:
            raise DatasetValidationError([{
                "code": "missing_document", "location": key,
                "message": "Replace requires employees.json, skills.json, events.json and activity_history.csv"
            } for key in sorted(missing)])
        return validate_dataset(dict(patch))

    catalog_keys = {"skills", "role_profiles", "proficiency_scale", "events"}.intersection(patch)
    if catalog_keys:
        raise DatasetValidationError([{
            "code": "catalog_requires_replace", "location": key,
            "message": "Catalog changes require a complete dataset replacement"
        } for key in sorted(catalog_keys)])
    if not {"employees", "history"}.intersection(patch):
        raise DatasetValidationError([{
            "code": "empty_upload", "location": "files",
            "message": "Append requires employees.json or activity_history.csv"
        }])
    content = base.model_dump()
    if "meta" in patch:
        meta = patch["meta"]
        meta = meta.model_dump() if hasattr(meta, "model_dump") else meta
        # Re-parse metadata with the Dataset schema, including date strings.
        try:
            candidate_meta = base.meta.__class__.model_validate(meta)
        except ValidationError as exc:
            raise DatasetValidationError(schema_issues(exc, "meta")) from exc
        if candidate_meta != base.meta:
            raise DatasetValidationError([{
                "code": "metadata_mismatch", "location": "meta",
                "message": "Append metadata must match the active dataset name, version and snapshot date"
            }])
    for name in ("employees", "history"):
        if name in patch:
            incoming = patch[name]
            if not isinstance(incoming, list):
                raise DatasetValidationError([{
                    "code": "schema_error", "location": name, "message": "Expected an array"
                }])
            content[name] = content[name] + [
                row.model_dump() if hasattr(row, "model_dump") else row for row in incoming
            ]
    return validate_dataset(content)
