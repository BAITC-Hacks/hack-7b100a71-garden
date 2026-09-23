"""Career targets, target gaps and readiness. No event ranking or API logic."""

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from math import fsum
from typing import Any, Dict, List, Tuple

from .config import DEFAULT_CONFIG, RecommendationConfig
from .contracts import (
    CalendarDate, CareerState, ReadinessResult, RecommendationInputError,
    SkillGap, TargetResolution,
)


def _name(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RecommendationInputError("invalid_identifier", "{} must be a nonempty string".format(field))
    return value


def _profile_index(role_profiles: Sequence) -> Dict[Tuple[str, str], Mapping]:
    if not isinstance(role_profiles, Sequence) or isinstance(role_profiles, (str, bytes)):
        raise RecommendationInputError("invalid_role_profiles", "Pass the role_profiles array, not its JSON wrapper")
    result = {}
    for profile in role_profiles:
        if not isinstance(profile, Mapping):
            raise RecommendationInputError("invalid_role_profile", "Each role profile must be a mapping")
        key = (_name(profile.get("role"), "profile.role"), _name(profile.get("grade"), "profile.grade"))
        if key in result:
            raise RecommendationInputError("duplicate_role_profile", "Duplicate role/grade profile: {} / {}".format(*key))
        result[key] = profile
    return result


def resolve_target(
    employee: Mapping,
    role_profiles: Sequence,
    *,
    config: RecommendationConfig = DEFAULT_CONFIG,
) -> TargetResolution:
    """Honor explicit targets first, then infer only an existing next grade."""
    if not isinstance(employee, Mapping):
        raise RecommendationInputError("invalid_employee", "Employee must be a mapping")
    profiles = _profile_index(role_profiles)
    role = _name(employee.get("role"), "employee.role")
    grade = _name(employee.get("grade"), "employee.grade")
    if grade not in config.grades:
        raise RecommendationInputError("unknown_grade", "Employee grade is not in the configured grade order")
    if (role, grade) not in profiles:
        raise RecommendationInputError("unknown_current_profile", "No profile for the employee's current role and grade")
    if "career_goal" not in employee:
        raise RecommendationInputError("missing_career_goal", "career_goal must be supplied explicitly, including null")
    goal = employee["career_goal"]
    if goal is not None:
        if not isinstance(goal, Mapping):
            raise RecommendationInputError("invalid_career_goal", "career_goal must be a mapping or null")
        target_role = _name(goal.get("target_role"), "career_goal.target_role")
        target_grade = _name(goal.get("target_grade"), "career_goal.target_grade")
        source = "career_goal"
    else:
        grade_index = config.grades.index(grade)
        if grade_index == len(config.grades) - 1:
            return {"status": "no_next_grade", "target": None}
        target_role = role
        target_grade = config.grades[grade_index + 1]
        source = "next_grade"
    if target_grade not in config.grades or (target_role, target_grade) not in profiles:
        raise RecommendationInputError("unknown_target_profile", "No configured profile for the requested target role and grade")
    return {"status": "resolved", "target": {"role": target_role, "grade": target_grade, "source": source}}


def _levels(values: Any, field: str, config: RecommendationConfig) -> Dict[str, int]:
    if not isinstance(values, Mapping):
        raise RecommendationInputError("invalid_skill_levels", "{} must be a skill-to-level mapping".format(field))
    result = {}
    for skill_id, level in values.items():
        _name(skill_id, "skill_id")
        if type(level) is not int or not config.skill_min_level <= level <= config.skill_max_level:
            raise RecommendationInputError("invalid_skill_level", "{} contains an invalid level for {}".format(field, skill_id))
        result[skill_id] = level
    return result


def _requirements(target_profile: Mapping, config: RecommendationConfig) -> Tuple[Dict[str, int], set]:
    if not isinstance(target_profile, Mapping):
        raise RecommendationInputError("invalid_role_profile", "Target profile must be a mapping")
    required = _levels(target_profile.get("required_skills"), "required_skills", config)
    critical = target_profile.get("critical_skills")
    if not isinstance(critical, Sequence) or isinstance(critical, (str, bytes)):
        raise RecommendationInputError("invalid_critical_skills", "critical_skills must be a sequence of skill IDs")
    for skill in critical:
        _name(skill, "critical_skills item")
    if len(set(critical)) != len(critical) or not set(critical).issubset(required):
        raise RecommendationInputError("invalid_critical_skills", "Critical skills must be unique members of required_skills")
    return required, set(critical)


def calculate_skill_gaps(
    effective_skills: Mapping,
    target_profile: Mapping,
    *,
    config: RecommendationConfig = DEFAULT_CONFIG,
) -> List[SkillGap]:
    """Return unmet target requirements; absent employee skills are level zero."""
    current = _levels(effective_skills, "effective_skills", config)
    required, critical = _requirements(target_profile, config)
    gaps = [
        {"skill_id": skill, "current": current.get(skill, 0), "required": level,
         "gap": level - current.get(skill, 0), "critical": skill in critical}
        for skill, level in required.items() if level > current.get(skill, 0)
    ]
    return sorted(gaps, key=lambda gap: (not gap["critical"], -gap["gap"], gap["skill_id"]))


def calculate_readiness(
    effective_skills: Mapping,
    target_profile: Mapping,
    *,
    config: RecommendationConfig = DEFAULT_CONFIG,
) -> ReadinessResult:
    """Capped target-requirement coverage, not guaranteed promotion eligibility."""
    current = _levels(effective_skills, "effective_skills", config)
    required, critical = _requirements(target_profile, config)
    ordered = sorted(required)
    weights = {skill: config.readiness_critical_weight if skill in critical else 1.0 for skill in ordered}
    denominator = fsum(weights[skill] * required[skill] for skill in ordered)
    numerator = fsum(weights[skill] * min(current.get(skill, 0), required[skill]) for skill in ordered)
    gaps = calculate_skill_gaps(current, target_profile, config=config)
    critical_gaps = [gap for gap in gaps if gap["critical"]]
    available = denominator > 0
    return {
        "current": numerator / denominator if available else None,
        "status": "available" if available else "unavailable",
        "reason": None if available else "no_positive_requirements",
        "critical_weight": config.readiness_critical_weight,
        "weighted_covered_levels": numerator,
        "weighted_required_levels": denominator,
        "critical_requirements_met": not critical_gaps if available else None,
        "remaining_critical_gaps": critical_gaps,
        "all_requirements_met": not gaps if available else None,
    }


def _as_date(value: CalendarDate) -> date:
    try:
        if isinstance(value, datetime):
            raise ValueError("Snapshot must be a calendar date")
        if isinstance(value, date):
            return value
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise RecommendationInputError("invalid_snapshot_date", "as_of must be a date or ISO calendar date") from None


def build_career_state(
    employee: Mapping,
    role_profiles: Sequence,
    events: Sequence,
    history: Sequence,
    *,
    as_of: CalendarDate,
    config: RecommendationConfig = DEFAULT_CONFIG,
) -> CareerState:
    """Step 1 facade for Bekarys's adapter; no eligibility, ranking, AI or I/O.

    Metadata's snapshot must be passed explicitly. This function never uses the
    system clock and never changes the review baseline or participation records.
    """
    from .skills import reconstruct_effective_skills

    if not isinstance(employee, Mapping):
        raise RecommendationInputError("invalid_employee", "Employee must be a mapping")
    employee_id = _name(employee.get("employee_id"), "employee_id")
    snapshot = _as_date(as_of)
    resolution = resolve_target(employee, role_profiles, config=config)
    reconstruction = reconstruct_effective_skills(employee, events, history, as_of=snapshot, config=config)
    target = resolution["target"]
    result = {
        "employee_id": employee_id,
        "as_of": snapshot.isoformat(),
        "status": "no_next_grade",
        "target": target,
        "skill_gaps": [],
        "career_readiness": None,
        "skills_reconstruction": reconstruction,
    }
    if target is None:
        return result
    profile = _profile_index(role_profiles)[(target["role"], target["grade"])]
    effective = reconstruction["effective_skills"]
    result["skill_gaps"] = calculate_skill_gaps(effective, profile, config=config)
    result["career_readiness"] = calculate_readiness(effective, profile, config=config)
    if result["career_readiness"]["status"] == "unavailable":
        result["status"] = "invalid_target_requirements"
    else:
        result["status"] = "target_satisfied" if result["career_readiness"]["all_requirements_met"] else "ok"
    return result
