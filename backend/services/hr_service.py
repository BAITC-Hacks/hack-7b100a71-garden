"""Aggregate current-role skill gaps and participation without personal rankings."""
from collections import Counter, defaultdict


STATUSES = ("completed", "in_progress", "dropped", "no_show", "declined", "overdue")


def build_hr_analytics(view, recommendation_coverage=None):
    employees = view.get_all_employees()
    catalog = {skill.skill_id: skill for skill in view.get_all_skills()}
    gaps = defaultdict(lambda: {"employee_count": 0, "total_levels_missing": 0,
                                "critical_employee_count": 0})
    for employee in employees:
        profile = view.get_role_profile(employee.role, employee.grade)
        levels = view.get_effective_skills(employee.employee_id)
        if profile is None:
            continue
        for skill_id, requirement in profile.required_skills.items():
            deficit = max(0, requirement - levels.get(skill_id, 0))
            if deficit:
                aggregate = gaps[skill_id]
                aggregate["employee_count"] += 1
                aggregate["total_levels_missing"] += deficit
                aggregate["critical_employee_count"] += int(skill_id in profile.critical_skills)
    common_gaps = [{"skill_id": skill_id, "skill_name": catalog[skill_id].name,
                    "category": catalog[skill_id].category, **values}
                   for skill_id, values in gaps.items()]
    common_gaps.sort(key=lambda gap: (-gap["employee_count"], -gap["total_levels_missing"], gap["skill_id"]))
    history = view.get_all_history()
    counts = Counter(record.status for record in history)
    participation = {status: counts[status] for status in STATUSES}
    event_map = {event.event_id: event for event in view.get_all_events()}
    voluntary = Counter(row.status for row in history if not event_map[row.event_id].mandatory)
    mandatory = Counter(row.status for row in history if event_map[row.event_id].mandatory)
    coverage = recommendation_coverage or {
        "available": False, "count": None, "evaluated_count": 0,
        "pending_count": len(employees), "complete": False,
    }
    return {
        "employee_count": len(employees),
        "gap_basis": "effective_skills_against_current_role_and_grade",
        "common_skill_gaps": common_gaps,
        "employees_without_next_step": coverage,
        "activity_participation": participation,
        "participation_summary": {
            "total_records": len(history),
            "participating_employees": len({row.employee_id for row in history}),
            "voluntary": {status: voluntary[status] for status in STATUSES},
            "mandatory": {status: mandatory[status] for status in STATUSES},
        },
    }
