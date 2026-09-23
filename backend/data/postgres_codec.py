"""Translate validated datasets to ordered relational rows and back.

The table order follows dependencies for convenient inserts. Foreign keys are
deferred in the migration so replacements can also remove dependent rows in a
single transaction. Positions retain the published dataset's list ordering.
"""
from typing import Any, Dict, List, Tuple

from backend.models.domain import Dataset, DatasetMeta


TABLE_KEYS: Dict[str, Tuple[str, ...]] = {
    "proficiency_scale": ("level",),
    "skills": ("skill_id",),
    "role_profiles": ("role", "grade"),
    "role_required_skills": ("role", "grade", "skill_id"),
    "role_critical_skills": ("role", "grade", "skill_id"),
    "employees": ("employee_id",),
    "employee_skills": ("employee_id", "skill_id"),
    "events": ("event_id",),
    "event_target_roles": ("event_id", "role"),
    "event_target_grades": ("event_id", "grade"),
    "event_gains": ("event_id", "skill_id"),
    "event_prerequisites": ("event_id", "skill_id"),
    "event_sessions": ("event_id", "session_date"),
    "activity_history": ("record_id",),
}

Rows = Dict[str, List[Dict[str, Any]]]


def encode_dataset(dataset: Dataset) -> Rows:
    """Return native Python values suitable for parameterized psycopg writes."""
    rows: Rows = {table: [] for table in TABLE_KEYS}
    rows["proficiency_scale"] = [
        {"level": int(level), "description": description}
        for level, description in dataset.proficiency_scale.items()
    ]
    rows["skills"] = [
        {**skill.model_dump(), "position": position}
        for position, skill in enumerate(dataset.skills)
    ]
    for position, profile in enumerate(dataset.role_profiles):
        key = {"role": profile.role, "grade": profile.grade}
        rows["role_profiles"].append({**key, "position": position})
        rows["role_required_skills"].extend(
            {**key, "skill_id": skill_id, "level": level, "position": index}
            for index, (skill_id, level) in enumerate(profile.required_skills.items())
        )
        rows["role_critical_skills"].extend(
            {**key, "skill_id": skill_id, "position": index}
            for index, skill_id in enumerate(profile.critical_skills)
        )

    for position, employee in enumerate(dataset.employees):
        row = employee.model_dump(exclude={"skills", "career_goal"})
        goal = employee.career_goal
        row.update(position=position, goal_role=goal.target_role if goal else None,
                   goal_grade=goal.target_grade if goal else None)
        rows["employees"].append(row)
        rows["employee_skills"].extend(
            {"employee_id": employee.employee_id, "skill_id": skill_id,
             "level": level, "position": index}
            for index, (skill_id, level) in enumerate(employee.skills.items())
        )

    event_relations = {"target_roles", "target_grades", "develops_skills",
                       "prerequisites", "upcoming_sessions"}
    for position, event in enumerate(dataset.events):
        rows["events"].append({**event.model_dump(exclude=event_relations),
                               "position": position})
        key = {"event_id": event.event_id}
        rows["event_target_roles"].extend(
            {**key, "role": role, "position": index}
            for index, role in enumerate(event.target_roles)
        )
        rows["event_target_grades"].extend(
            {**key, "grade": grade, "position": index}
            for index, grade in enumerate(event.target_grades)
        )
        rows["event_gains"].extend(
            {**key, **gain.model_dump(), "position": index}
            for index, gain in enumerate(event.develops_skills)
        )
        rows["event_prerequisites"].extend(
            {**key, "skill_id": skill_id, "level": level, "position": index}
            for index, (skill_id, level) in enumerate(event.prerequisites.items())
        )
        rows["event_sessions"].extend(
            {**key, "session_date": session, "position": index}
            for index, session in enumerate(event.upcoming_sessions)
        )
    rows["activity_history"] = [
        {**record.model_dump(), "position": position}
        for position, record in enumerate(dataset.history)
    ]
    return rows


def decode_dataset(rows: Rows, meta: DatasetMeta) -> Dataset:
    """Reconstruct an independent dataset without relying on SELECT row order."""
    def ordered(table):
        return sorted(rows.get(table, []), key=lambda row: row["position"])

    def scalars(row, *excluded):
        return {key: value for key, value in row.items()
                if key != "position" and key not in excluded}

    def group(table, key_columns):
        grouped = {}
        for row in ordered(table):
            key = tuple(row[column] for column in key_columns)
            grouped.setdefault(key, []).append(row)
        return grouped

    required = group("role_required_skills", ("role", "grade"))
    critical = group("role_critical_skills", ("role", "grade"))
    profiles = []
    for row in ordered("role_profiles"):
        key = (row["role"], row["grade"])
        profiles.append({
            **scalars(row),
            "required_skills": {item["skill_id"]: item["level"]
                                for item in required.get(key, [])},
            "critical_skills": [item["skill_id"] for item in critical.get(key, [])],
        })

    assessed = group("employee_skills", ("employee_id",))
    employees = []
    for row in ordered("employees"):
        goal = ({"target_role": row["goal_role"], "target_grade": row["goal_grade"]}
                if row["goal_role"] is not None else None)
        employees.append({
            **scalars(row, "goal_role", "goal_grade"), "career_goal": goal,
            "skills": {item["skill_id"]: item["level"]
                       for item in assessed.get((row["employee_id"],), [])},
        })

    roles = group("event_target_roles", ("event_id",))
    grades = group("event_target_grades", ("event_id",))
    gains = group("event_gains", ("event_id",))
    prerequisites = group("event_prerequisites", ("event_id",))
    sessions = group("event_sessions", ("event_id",))
    events = []
    for row in ordered("events"):
        key = (row["event_id"],)
        events.append({
            **scalars(row),
            "target_roles": [item["role"] for item in roles.get(key, [])],
            "target_grades": [item["grade"] for item in grades.get(key, [])],
            "develops_skills": [scalars(item, "event_id") for item in gains.get(key, [])],
            "prerequisites": {item["skill_id"]: item["level"]
                              for item in prerequisites.get(key, [])},
            "upcoming_sessions": [item["session_date"] for item in sessions.get(key, [])],
        })

    return Dataset.model_validate({
        "meta": meta.model_dump(),
        "proficiency_scale": {str(row["level"]): row["description"] for row in
                              sorted(rows.get("proficiency_scale", []),
                                     key=lambda row: row["level"])},
        "skills": [scalars(row) for row in ordered("skills")],
        "role_profiles": profiles,
        "employees": employees,
        "events": events,
        "history": [scalars(row) for row in ordered("activity_history")],
    })
