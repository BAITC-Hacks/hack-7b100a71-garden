"""Hypothetical event completion and target impact, without admission or ranking."""

from collections.abc import Mapping

from .career import (
    _levels,
    _name,
    _requirements,
    calculate_readiness,
    calculate_skill_gaps,
)
from .config import DEFAULT_CONFIG, RecommendationConfig
from .contracts import EventSimulation
from .skills import _event_index


def simulate_event(
    effective_skills: Mapping,
    target_profile: Mapping,
    event: Mapping,
    *,
    config: RecommendationConfig = DEFAULT_CONFIG,
) -> EventSimulation:
    """Apply one event to an independent skill copy and describe its impact.

    This function can also simulate ineligible or irrelevant activities: it does
    not inspect the employee's audience, participation history or availability.
    Missing skill levels mean zero. Positive gains beyond a destination
    requirement remain visible as actual gains but do not close target gaps.
    """
    before = _levels(effective_skills, "effective_skills", config)
    required, critical = _requirements(target_profile, config)
    target = {
        "role": _name(target_profile.get("role"), "profile.role"),
        "grade": _name(target_profile.get("grade"), "profile.grade"),
    }
    _event_index([event], config)
    after = dict(before)
    skill_impact = []
    target_skill_impact = []
    requirements_closed = []
    critical_requirements_closed = []

    for development in sorted(event["develops_skills"], key=lambda item: item["skill_id"]):
        skill_id = development["skill_id"]
        current = before.get(skill_id, 0)
        gain = min(development["gain"], max(0, development["max_level"] - current))
        updated = current + gain
        after[skill_id] = updated
        skill_impact.append({
            "skill_id": skill_id,
            "before": current,
            "advertised_gain": development["gain"],
            "max_level": development["max_level"],
            "after": updated,
            "actual_gain": gain,
        })
        if skill_id not in required:
            continue
        gap_before = max(required[skill_id] - current, 0)
        gap_after = max(required[skill_id] - updated, 0)
        target_skill_impact.append({
            "skill_id": skill_id,
            "current": current,
            "required": required[skill_id],
            "gap_before": gap_before,
            "after": updated,
            "gap_after": gap_after,
            "useful_gain": gap_before - gap_after,
            "critical": skill_id in critical,
        })
        if gap_before > 0 and gap_after == 0:
            requirements_closed.append(skill_id)
            if skill_id in critical:
                critical_requirements_closed.append(skill_id)

    gaps_before = calculate_skill_gaps(before, target_profile, config=config)
    gaps_after = calculate_skill_gaps(after, target_profile, config=config)
    critical_before = [dict(gap) for gap in gaps_before if gap["critical"]]
    critical_after = [dict(gap) for gap in gaps_after if gap["critical"]]
    total_gap_before = sum(gap["gap"] for gap in gaps_before)
    total_gap_after = sum(gap["gap"] for gap in gaps_after)
    critical_gap_before = sum(gap["gap"] for gap in critical_before)
    critical_gap_after = sum(gap["gap"] for gap in critical_after)
    readiness_before = calculate_readiness(before, target_profile, config=config)
    readiness_after = calculate_readiness(after, target_profile, config=config)
    before_value = readiness_before["current"]
    after_value = readiness_after["current"]

    return {
        "event_id": event["event_id"],
        "target": target,
        "simulated_skills_after": dict(sorted(after.items())),
        "skill_impact": skill_impact,
        "target_skill_impact": target_skill_impact,
        "skill_gaps_before": gaps_before,
        "skill_gaps_after": gaps_after,
        "critical_gaps_before": critical_before,
        "critical_gaps_after": critical_after,
        "total_gap_before": total_gap_before,
        "total_gap_after": total_gap_after,
        "total_gap_reduction": total_gap_before - total_gap_after,
        "critical_gap_before": critical_gap_before,
        "critical_gap_after": critical_gap_after,
        "critical_gap_reduction": critical_gap_before - critical_gap_after,
        "requirements_closed": requirements_closed,
        "critical_requirements_closed": critical_requirements_closed,
        "readiness_before": before_value,
        "readiness_after": after_value,
        "readiness_delta": (
            after_value - before_value
            if before_value is not None and after_value is not None else None
        ),
        "readiness_before_details": readiness_before,
        "readiness_after_details": readiness_after,
    }
