"""Seven-factor scoring over the complete eligible pool, without ranking or I/O."""

from collections.abc import Mapping, Sequence
from math import fsum, isfinite
from typing import List

from .config import DEFAULT_CONFIG, RecommendationConfig
from .contracts import RecommendationInputError, ScoredCandidate
from .skills import _calendar_date, _event_index, _identifier, _require_sequence


def _error(code, message):
    raise RecommendationInputError(code, message)


def _nonnegative_int(value, field):
    if type(value) is not int or value < 0:
        _error("invalid_simulation", "{} must be a nonnegative integer".format(field))
    return value


def _unit_signal(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _error("invalid_history_signal", "{} must be a finite number in [0, 1]".format(field))
    try:
        valid = isfinite(value) and 0 <= value <= 1
    except OverflowError:
        valid = False
    if not valid:
        _error("invalid_history_signal", "{} must be a finite number in [0, 1]".format(field))
    return value


def _simulation_values(candidate, config):
    simulation = candidate.get("simulation")
    if not isinstance(simulation, Mapping) or simulation.get("event_id") != candidate["event_id"]:
        _error("invalid_simulation", "Candidate must contain its own Step 2 simulation")
    totals = {}
    for prefix in ("total", "critical"):
        before, after, reduction = [
            _nonnegative_int(simulation.get(prefix + "_gap_" + suffix), prefix + "_gap_" + suffix)
            for suffix in ("before", "after", "reduction")
        ]
        if before - after != reduction:
            _error("invalid_simulation", "Gap reductions must agree with before/after evidence")
        totals[prefix] = (before, after, reduction)
    if any(critical > total for critical, total in zip(totals["critical"], totals["total"])):
        _error("invalid_simulation", "Critical gap quantities cannot exceed total gaps")

    impacts = simulation.get("skill_impact")
    _require_sequence(impacts, "skill_impact", "invalid_simulation")
    actual_by_skill = {}
    for impact in impacts:
        if not isinstance(impact, Mapping):
            _error("invalid_simulation", "Each skill impact must be a mapping")
        skill_id = _identifier(impact.get("skill_id"), "skill_impact.skill_id")
        actual = _nonnegative_int(impact.get("actual_gain"), "actual_gain")
        if skill_id in actual_by_skill or actual > config.skill_max_level:
            _error("invalid_simulation", "Actual gains must be unique per skill and within the level scale")
        actual_by_skill[skill_id] = actual

    target_impacts = simulation.get("target_skill_impact")
    _require_sequence(target_impacts, "target_skill_impact", "invalid_simulation")
    useful_by_skill = {}
    critical_gains = []
    for impact in target_impacts:
        if not isinstance(impact, Mapping):
            _error("invalid_simulation", "Each target impact must be a mapping")
        skill_id = _identifier(impact.get("skill_id"), "target_skill_impact.skill_id")
        useful = _nonnegative_int(impact.get("useful_gain"), "useful_gain")
        if skill_id in useful_by_skill or skill_id not in actual_by_skill or useful > actual_by_skill[skill_id]:
            _error("invalid_simulation", "Useful gain must occur once and cannot exceed the skill's actual gain")
        if type(impact.get("critical")) is not bool:
            _error("invalid_simulation", "Target impact critical flag must be boolean")
        useful_by_skill[skill_id] = useful
        if impact["critical"]:
            critical_gains.append(useful)
    useful = sum(useful_by_skill.values())
    if useful != totals["total"][2] or sum(critical_gains) != totals["critical"][2]:
        _error("invalid_simulation", "Per-skill useful gains must equal the total and critical reductions")
    return totals["critical"][2], totals["total"][2], useful, sum(actual_by_skill.values())


def _efficiency(raw_duration, gap_reduction):
    """Invalid or unrepresentable durations contribute zero, never infinity."""
    if isinstance(raw_duration, bool) or not isinstance(raw_duration, (str, int, float)):
        return None, 0.0
    try:
        duration = float(raw_duration)
        if not isfinite(duration) or duration <= 0:
            return None, 0.0
        efficiency = gap_reduction / duration
        if not isfinite(efficiency):
            return None, 0.0
    except (TypeError, ValueError, OverflowError):
        return None, 0.0
    return duration, efficiency


def _availability(candidate, event, config):
    evidence = candidate.get("evidence")
    availability = evidence.get("availability") if isinstance(evidence, Mapping) else None
    if not isinstance(availability, Mapping) or availability.get("available") is not True:
        _error("invalid_availability", "Eligible candidates must contain available Step 2 evidence")
    self_paced = availability.get("self_paced")
    if type(self_paced) is not bool or self_paced != (event["format"] == "self_paced"):
        _error("invalid_availability", "Self-paced evidence must agree with the catalog event")
    if availability.get("format") != event["format"]:
        _error("invalid_availability", "Availability format must agree with the catalog event")
    days = availability.get("days_until_next_session")
    if type(days) is not int or days < 0:
        _error("invalid_availability", "Waiting days must be a nonnegative integer")
    if self_paced:
        if days != 0 or availability.get("next_session_date") is not None:
            _error("invalid_availability", "Self-paced availability has no session date or waiting time")
        return 1.0, days
    _calendar_date(availability.get("next_session_date"), "next_session_date")
    try:
        value = 1 / (1 + days / config.availability_wait_scale_days)
    except OverflowError:
        value = 0.0
    return min(1.0, max(0.0, value)), days


def score_candidates(
    candidates: Sequence,
    events: Sequence,
    history_signals: Mapping,
    *,
    config: RecommendationConfig = DEFAULT_CONFIG,
) -> List[ScoredCandidate]:
    """Score all eligible candidates together and return them in event-ID order.

    C/G/E maxima use the complete supplied pool. The caller must not truncate it
    before this call. Ranking and top-N selection belong to the engine. R's
    ``advertised_positive_gain`` field follows the approved formula: it is the
    sum of positive *actual simulated gains*, after event caps, not nominal gains.
    """
    _require_sequence(candidates, "candidates", "invalid_candidates")
    _require_sequence(events, "events", "invalid_events")
    event_index = _event_index(events, config)
    if not isinstance(history_signals, Mapping):
        _error("invalid_history_signals", "History signals must map event IDs to their signals")
    prepared = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            _error("invalid_candidate", "Each candidate must be a Step 2 eligibility mapping")
        event_id = _identifier(candidate.get("event_id"), "candidate.event_id")
        if event_id in prepared:
            _error("duplicate_candidate", "Duplicate eligible candidate: {}".format(event_id))
        if candidate.get("eligible") is not True or candidate.get("rejection_reasons") != []:
            _error("ineligible_candidate", "Scoring accepts only candidates admitted by Step 2")
        if event_id not in event_index:
            _error("unknown_event", "Candidate is absent from the event catalog: {}".format(event_id))
        signal = history_signals.get(event_id)
        if not isinstance(signal, Mapping):
            _error("missing_history_signal", "Supply history signals for candidate {}".format(event_id))
        compatibility = _unit_signal(signal.get("compatibility"), "compatibility")
        feedback = _unit_signal(signal.get("feedback_signal"), "feedback_signal")
        critical, total, useful, positive_actual = _simulation_values(candidate, config)
        duration, efficiency = _efficiency(event_index[event_id].get("duration_hours"), total)
        availability, days = _availability(candidate, event_index[event_id], config)
        relevance = min(1.0, max(0.0, useful / positive_actual)) if positive_actual else 0.0
        prepared[event_id] = {
            "raw": {
                "critical_skill_impact": critical, "gap_reduction": total,
                "career_relevance": relevance, "historical_compatibility": compatibility,
                "history_feedback_signal": feedback, "effort_efficiency": efficiency,
                "availability": availability,
            },
            "scoring_evidence": {
                "useful_destination_gain": useful,
                "advertised_positive_gain": positive_actual,
                "duration_hours": duration, "duration_valid": duration is not None,
                "raw_efficiency": efficiency, "availability_wait_days": days,
                "normalization_candidate_count": len(candidates),
            },
        }
    maxima = {
        name: max((item["raw"][name] for item in prepared.values()), default=0.0)
        for name in ("critical_skill_impact", "gap_reduction", "effort_efficiency")
    }
    scored = []
    for event_id in sorted(prepared):
        item = prepared[event_id]
        factors = {}
        for name, weight in vars(config.scoring_weights).items():
            raw = item["raw"][name]
            if name in maxima:
                normalized = raw / maxima[name] if maxima[name] > 0 else 0.0
            else:
                normalized = raw
            factors[name] = {
                "raw": raw, "normalized": normalized, "weight": weight,
                "contribution": normalized * weight,
            }
        item["scoring_evidence"]["normalization_maxima"] = dict(maxima)
        scored.append({
            "event_id": event_id,
            "score": fsum(factor["contribution"] for factor in factors.values()),
            "factors": factors, "scoring_evidence": item["scoring_evidence"],
        })
    return scored
