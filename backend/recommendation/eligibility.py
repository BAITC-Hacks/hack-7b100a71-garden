"""Explainable event admission and hypothetical impact; no scoring or ranking."""

from collections.abc import Mapping, Sequence
from typing import Optional

from .career import _levels, _profile_index, _requirements, resolve_target
from .config import DEFAULT_CONFIG, RecommendationConfig
from .contracts import CalendarDate, CatalogEligibility, EligibilityResult, RecommendationInputError
from .simulation import simulate_event
from .skills import _calendar_date, _completion_time, _event_index, _identifier, _require_sequence


def _error(code, message):
    raise RecommendationInputError(code, message)


def _context(employee, career_state, target_profile, as_of, config):
    if not isinstance(employee, Mapping) or not isinstance(career_state, Mapping):
        _error("invalid_career_context", "employee and career_state must be mappings")
    snapshot = _calendar_date(as_of, "as_of")
    employee_id = _identifier(employee.get("employee_id"), "employee_id")
    if career_state.get("employee_id") != employee_id:
        _error("career_state_employee_mismatch", "CareerState belongs to another employee")
    if _calendar_date(career_state.get("as_of"), "career_state.as_of") != snapshot:
        _error("career_state_snapshot_mismatch", "Rebuild CareerState for the requested snapshot")
    role = _identifier(employee.get("role"), "employee.role")
    grade = _identifier(employee.get("grade"), "employee.grade")
    if grade not in config.grades:
        _error("unknown_grade", "Attained grade is not in the configured grade order")
    if "career_goal" not in employee or "target" not in career_state:
        _error("missing_career_context", "Supply career_goal (including null) and resolved target")
    goal = employee["career_goal"]
    target = career_state["target"]
    if target is None:
        if goal is not None or grade != config.grades[-1]:
            _error("career_state_target_mismatch", "The supplied employee should have a resolved career target")
        if target_profile is not None:
            _error("unexpected_target_profile", "A missing career target must not have a target profile")
    else:
        if not isinstance(target, Mapping):
            _error("invalid_career_target", "Resolved target must be a mapping or null")
        target_role = _identifier(target.get("role"), "target.role")
        target_grade = _identifier(target.get("grade"), "target.grade")
        if target_grade not in config.grades:
            _error("unknown_grade", "Target grade is not configured")
        if target.get("source") == "career_goal":
            if not isinstance(goal, Mapping) or (goal.get("target_role"), goal.get("target_grade")) != (target_role, target_grade):
                _error("career_state_target_mismatch", "Resolved target differs from the employee's explicit goal")
        elif target.get("source") == "next_grade":
            position = config.grades.index(grade)
            if goal is not None or position == len(config.grades) - 1 or (target_role, target_grade) != (role, config.grades[position + 1]):
                _error("career_state_target_mismatch", "Resolved inferred target differs from the attained grade policy")
        else:
            _error("invalid_target_source", "Target source must be career_goal or next_grade")
        if not isinstance(target_profile, Mapping) or (target_profile.get("role"), target_profile.get("grade")) != (target_role, target_grade):
            _error("target_profile_mismatch", "Target requirements must match the resolved role and grade")
        _requirements(target_profile, config)
        target = dict(target)
    reconstruction = career_state.get("skills_reconstruction")
    if not isinstance(reconstruction, Mapping):
        _error("invalid_career_context", "Supply the Step 1 skills_reconstruction result")
    effective = _levels(reconstruction.get("effective_skills"), "effective_skills", config)
    estimate = reconstruction.get("is_estimate")
    if type(estimate) is not bool:
        _error("invalid_career_context", "skills_reconstruction.is_estimate must be a boolean")
    readiness = career_state.get("career_readiness")
    if readiness is not None:
        if not isinstance(readiness, Mapping):
            _error("invalid_career_context", "career_readiness must be a Step 1 result or null")
        if readiness.get("critical_weight") != config.readiness_critical_weight:
            _error("career_state_config_mismatch", "Use the same critical readiness weight as Step 1")
    return {
        "snapshot": snapshot, "employee_id": employee_id, "role": role, "grade": grade,
        "target": target, "effective": effective, "estimate": estimate,
    }


def _audience(values, field):
    _require_sequence(values, field, "invalid_audience")
    return {_identifier(value, field) for value in values}


def _participation_index(history, employee_id, snapshot, config):
    """Keep attempts separate and use only facts dated on/before the snapshot."""
    _require_sequence(history, "history", "invalid_history")
    seen = {}
    by_event = {}
    for record in history:
        if not isinstance(record, Mapping):
            _error("invalid_history", "Each participation must be a mapping")
        if record.get("employee_id") != employee_id:
            continue
        record_id = _identifier(record.get("record_id"), "record_id")
        if record_id in seen:
            if record != seen[record_id]:
                _error("conflicting_record_id", "Conflicting participation ID: {}".format(record_id))
            continue
        seen[record_id] = record
        event_id = _identifier(record.get("event_id"), "history.event_id")
        status = record.get("status")
        if status not in config.history_statuses:
            _error("invalid_history_status", "Unknown status on {}".format(record_id))
        participation, participation_order, participation_has_time = _completion_time(record.get("date"), "history.date")
        evidence_date = participation
        completed_at = record.get("completed_at")
        if completed_at is not None and completed_at != "":
            if status != "completed":
                _error("completion_on_noncompleted_record", "Only completed participations can have completed_at")
            evidence_date, completion_order, completion_has_time = _completion_time(completed_at, "completed_at")
            precedes_participation = completion_order < participation_order if completion_has_time and participation_has_time else evidence_date < participation
            if precedes_participation:
                _error("completion_before_participation", "Completion precedes participation on {}".format(record_id))
        facts = by_event.setdefault(event_id, {
            "completed_record_ids": [], "in_progress_record_ids": [], "ignored_future_record_ids": [],
        })
        if participation > snapshot or evidence_date > snapshot:
            facts["ignored_future_record_ids"].append(record_id)
        elif status == "completed":
            facts["completed_record_ids"].append(record_id)
        elif status == "in_progress":
            facts["in_progress_record_ids"].append(record_id)
    for facts in by_event.values():
        for ids in facts.values():
            ids.sort()
    return by_event


def _availability(event, snapshot):
    _require_sequence(event.get("upcoming_sessions"), "upcoming_sessions", "invalid_sessions")
    sessions = sorted({_calendar_date(value, "upcoming_sessions item") for value in event["upcoming_sessions"]})
    self_paced = event["format"] == "self_paced"
    future = [day for day in sessions if day >= snapshot]
    next_date = future[0] if future and not self_paced else None
    return {
        "format": event["format"], "available": self_paced or bool(future),
        "self_paced": self_paced,
        "next_session_date": next_date.isoformat() if next_date else None,
        "days_until_next_session": 0 if self_paced else (next_date - snapshot).days if next_date else None,
        "valid_session_dates": [] if self_paced else [day.isoformat() for day in future],
    }


def _evaluate(context, target_profile, event, participation_index, config):
    mandatory = event.get("mandatory")
    if type(mandatory) is not bool:
        _error("invalid_mandatory", "event.mandatory must be an explicit boolean")
    roles = _audience(event.get("target_roles"), "target_roles")
    grades = _audience(event.get("target_grades"), "target_grades")
    prerequisites = _levels(event.get("prerequisites"), "prerequisites", config)
    current_match = context["role"] in roles
    target = context["target"]
    target_match = bool(target and target["source"] == "career_goal" and target["role"] in roles)
    audience_match = "both" if current_match and target_match else "current_role" if current_match else "target_role" if target_match else None
    grade_match = context["grade"] in grades
    checks = [
        {"skill_id": skill, "current": context["effective"].get(skill, 0), "required": level,
         "met": context["effective"].get(skill, 0) >= level}
        for skill, level in sorted(prerequisites.items())
    ]
    event_id = event["event_id"]
    facts = participation_index.get(event_id, {})
    history_evidence = {
        "completed_record_ids": list(facts.get("completed_record_ids", [])),
        "in_progress_record_ids": list(facts.get("in_progress_record_ids", [])),
        "ignored_future_record_ids": list(facts.get("ignored_future_record_ids", [])),
        "recurring_exception": not mandatory and event_id in config.recurring_event_ids,
    }
    availability = _availability(event, context["snapshot"])
    # Also simulate rejected activities with a target: this is a hypothetical
    # explanation of impact, never an assertion that enrollment is allowed.
    simulation = simulate_event(context["effective"], target_profile, event, config=config) if target is not None else None
    reasons = []

    def reject(code, message):
        reasons.append({"code": code, "message": message})

    if mandatory:
        reject("MANDATORY", "Mandatory activities are not recommendation candidates.")
    if audience_match is None:
        reject("ROLE_MISMATCH", "Neither the current role nor an explicit destination role matches the audience.")
    if not grade_match:
        reject("GRADE_MISMATCH", "The employee's attained current grade is outside the event audience.")
    if any(not check["met"] for check in checks):
        reject("PREREQUISITE_NOT_MET", "At least one prerequisite is unmet by reconstructed effective skills.")
    if not mandatory and history_evidence["completed_record_ids"] and not history_evidence["recurring_exception"]:
        reject("ALREADY_COMPLETED", "This nonrecurring voluntary activity was already completed.")
    if history_evidence["in_progress_record_ids"]:
        reject("ALREADY_IN_PROGRESS", "At least one separate participation is still in progress.")
    if target is None:
        reject("NO_CAREER_TARGET", "No resolved career target is available for gap-based recommendations.")
    elif simulation["total_gap_reduction"] <= 0:
        reject("NO_TARGET_GAP_IMPACT", "Completion would not reduce any destination requirement gap after caps.")
    if not availability["available"]:
        reject("NO_UPCOMING_SESSION", "No scheduled session is available on or after the snapshot date.")
    title = event.get("title", event_id)
    _identifier(title, "event.title")
    return {
        "event_id": event_id, "title": title, "eligible": not reasons,
        "rejection_reasons": reasons,
        "evidence": {
            "current_role": context["role"],
            "target_role": target["role"] if target else None,
            "target_grade": target["grade"] if target else None,
            "audience_match": audience_match,
            "attained_grade": context["grade"],
            "matched_current_grade": context["grade"] if grade_match else None,
            "prerequisite_checks": checks, "history": history_evidence,
            "availability": availability, "skills_are_estimated": context["estimate"],
        },
        "simulation": simulation,
    }


def evaluate_event(
    employee: Mapping,
    career_state: Mapping,
    target_profile: Optional[Mapping],
    event: Mapping,
    history: Sequence,
    *,
    as_of: CalendarDate,
    config: RecommendationConfig = DEFAULT_CONFIG,
) -> EligibilityResult:
    """Evaluate every safe admission rule, returning all reasons and raw impact.

    Uses the supplied Step 1 state; callers must rebuild it after history/skills
    change. This function does not reconstruct history a second time.
    """
    context = _context(employee, career_state, target_profile, as_of, config)
    _event_index([event], config)
    history_index = _participation_index(history, context["employee_id"], context["snapshot"], config)
    return _evaluate(context, target_profile, event, history_index, config)


def evaluate_catalog(
    employee: Mapping,
    career_state: Mapping,
    role_profiles: Sequence,
    events: Sequence,
    history: Sequence,
    *,
    as_of: CalendarDate,
    config: RecommendationConfig = DEFAULT_CONFIG,
) -> CatalogEligibility:
    """Partition the catalog by eligibility, in event-ID order, without ranking."""
    if not isinstance(career_state, Mapping):
        _error("invalid_career_context", "career_state must be a mapping")
    resolution = resolve_target(employee, role_profiles, config=config)
    if resolution["target"] != career_state.get("target"):
        _error("career_state_target_mismatch", "Rebuild CareerState for the employee's current goal")
    profiles = _profile_index(role_profiles)
    target = resolution["target"]
    target_profile = profiles[(target["role"], target["grade"])] if target else None
    context = _context(employee, career_state, target_profile, as_of, config)
    _require_sequence(events, "events", "invalid_events")
    event_index = _event_index(events, config)
    history_index = _participation_index(history, context["employee_id"], context["snapshot"], config)
    evaluations = [_evaluate(context, target_profile, event_index[event_id], history_index, config) for event_id in sorted(event_index)]
    eligible = [evaluation for evaluation in evaluations if evaluation["eligible"]]
    rejected = [evaluation for evaluation in evaluations if not evaluation["eligible"]]
    return {
        "employee_id": context["employee_id"], "as_of": context["snapshot"].isoformat(),
        "target": context["target"], "event_count": len(evaluations),
        "eligible_count": len(eligible), "rejected_count": len(rejected),
        "eligible_candidates": eligible, "rejected_events": rejected,
    }
