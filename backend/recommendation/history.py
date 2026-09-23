"""Smoothed learning-preference signals, independent of admission and ranking.

Only aggregate evidence is returned by default. Record-level mathematical
evidence is opt-in for backend debugging; it contains no free-text feedback.
Unknown assignment sources use the configured neutral source weight. Missing or
malformed optional ratings/assessments never become zero-valued observations.
"""

from collections.abc import Mapping
from math import fsum, isfinite

from .config import DEFAULT_CONFIG, RecommendationConfig
from .contracts import CalendarDate, HistorySignals, RecommendationInputError
from .skills import (
    _calendar_date, _participation_timing, _event_index, _identifier, _require_sequence,
)


def _optional_number(value, minimum, maximum):
    """Return (valid numeric observation or None, missing/invalid/valid)."""
    if value is None or isinstance(value, str) and not value.strip():
        return None, "missing"
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None, "invalid"
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None, "invalid"
    if not isfinite(number) or not minimum <= number <= maximum:
        return None, "invalid"
    return number, "valid"


def _similarity(candidate, historical, policy):
    candidate_skills = {item["skill_id"] for item in candidate["develops_skills"]}
    historical_skills = {item["skill_id"] for item in historical["develops_skills"]}
    union = candidate_skills | historical_skills
    jaccard = len(candidate_skills & historical_skills) / len(union) if union else 0.0
    candidate_type = candidate.get("type")
    same_type = bool(isinstance(candidate_type, str) and candidate_type.strip()
                     and candidate_type == historical.get("type"))
    same_format = candidate["format"] == historical["format"]
    similarity = fsum((
        policy.skill_similarity_weight * jaccard,
        policy.type_similarity_weight * same_type,
        policy.format_similarity_weight * same_format,
    ))
    return jaccard, same_type, same_format, similarity


def _record_time(record):
    participation, completion, _, _, sequence = _participation_timing(record)
    completed_at = record.get("completed_at")
    if completed_at is None or completed_at == "":
        return participation, participation, "participation_date"
    return participation, completion, "runtime_completed_on" if sequence is not None else "completed_at"


def calculate_history_signals(
    employee_id: str,
    candidate_event: Mapping,
    events,
    history,
    *,
    as_of: CalendarDate,
    config: RecommendationConfig = DEFAULT_CONFIG,
    include_records: bool = False,
) -> HistorySignals:
    """Return H/F in [0, 1] using separate, deterministically sorted attempts.

    ``matched_history_count`` counts usable records with positive effective
    weight. Positive/negative weights sum weights whose outcome is above/below
    the configured H prior, rather than summing weight times outcome. Recent
    counters additionally require the configured similarity and age thresholds.
    Feedback observation and malformed-value counts refer to matched records.

    History snapshot boundaries follow the stated calendar date, matching skill
    reconstruction. A completed_at extension supplies completed-record recency;
    otherwise the available participation date is the documented proxy.
    """
    _identifier(employee_id, "employee_id")
    snapshot = _calendar_date(as_of, "as_of")
    _require_sequence(events, "events", "invalid_events")
    _require_sequence(history, "history", "invalid_history")
    if type(include_records) is not bool:
        raise RecommendationInputError("invalid_include_records", "include_records must be boolean")
    event_index = _event_index(events, config)
    _event_index([candidate_event], config)
    policy = config.history
    source_weights = dict(policy.source_weights)
    outcomes = dict(policy.status_outcomes)
    unique = {}
    for record in history:
        if not isinstance(record, Mapping):
            raise RecommendationInputError("invalid_history", "Each participation must be a mapping")
        if record.get("employee_id") != employee_id:
            continue
        record_id = _identifier(record.get("record_id"), "history.record_id")
        if record_id in unique and record != unique[record_id]:
            raise RecommendationInputError("conflicting_record_id", "Conflicting participation ID: " + record_id)
        unique[record_id] = record

    evidence = {
        "considered_history_count": len(unique),
        "matched_history_count": 0,
        "effective_history_weight": 0.0,
        "positive_weight": 0.0,
        "negative_weight": 0.0,
        "recent_similar_no_shows": 0,
        "recent_similar_completions": 0,
        "rating_observation_count": 0,
        "assessment_observation_count": 0,
        "feedback_record_count": 0,
        "effective_feedback_weight": 0.0,
        "excluded_mandatory_count": 0,
        "excluded_status_count": 0,
        "ignored_future_count": 0,
        "zero_similarity_count": 0,
        "zero_weight_count": 0,
        "unknown_source_count": 0,
        "missing_rating_count": 0,
        "missing_assessment_count": 0,
        "invalid_rating_count": 0,
        "invalid_assessment_count": 0,
        "completion_date_proxy_count": 0,
        "priors": {
            "compatibility_value": policy.neutral_value,
            "compatibility_weight": policy.prior_weight,
            "feedback_value": policy.feedback_neutral_value,
            "feedback_weight": policy.feedback_prior_weight,
        },
        "config_snapshot": {
            "skill_similarity_weight": policy.skill_similarity_weight,
            "type_similarity_weight": policy.type_similarity_weight,
            "format_similarity_weight": policy.format_similarity_weight,
            "recency_half_life_days": policy.recency_half_life_days,
            "source_weights": dict(policy.source_weights),
            "unknown_source_weight": policy.unknown_source_weight,
            "status_outcomes": dict(policy.status_outcomes),
            "excluded_statuses": list(policy.excluded_statuses),
            "include_mandatory": policy.include_mandatory,
            "history_prior_weight": policy.prior_weight,
            "history_prior_value": policy.neutral_value,
            "feedback_prior_weight": policy.feedback_prior_weight,
            "feedback_prior_value": policy.feedback_neutral_value,
            "recent_window_days": policy.recent_window_days,
            "recent_similarity_threshold": policy.recent_similarity_threshold,
        },
    }
    weights, weighted_outcomes, positive, negative = [], [], [], []
    feedback_weights, weighted_feedback = [], []
    record_evidence = []
    for record_id, record in sorted(unique.items()):
        status = record.get("status")
        if status not in config.history_statuses:
            raise RecommendationInputError("invalid_history_status", "Unknown status on " + record_id)
        event_id = _identifier(record.get("event_id"), "history.event_id")
        if event_id not in event_index:
            raise RecommendationInputError("unknown_event", "History references unknown event " + event_id)
        historical_event = event_index[event_id]
        if type(historical_event.get("mandatory")) is not bool:
            raise RecommendationInputError("invalid_mandatory", "Historical event.mandatory must be boolean")
        participation, evidence_date, date_basis = _record_time(record)
        if participation > snapshot or evidence_date > snapshot:
            evidence["ignored_future_count"] += 1
            continue
        if historical_event["mandatory"] and not policy.include_mandatory:
            evidence["excluded_mandatory_count"] += 1
            continue
        if status in policy.excluded_statuses or status not in outcomes:
            evidence["excluded_status_count"] += 1
            continue
        jaccard, same_type, same_format, similarity = _similarity(candidate_event, historical_event, policy)
        if similarity == 0:
            evidence["zero_similarity_count"] += 1
            continue
        source = record.get("assigned_by")
        known_source = isinstance(source, str) and source in source_weights
        source_weight = source_weights[source] if known_source else policy.unknown_source_weight
        if not known_source:
            evidence["unknown_source_count"] += 1
        age_days = (snapshot - evidence_date).days
        recency = 2 ** (-age_days / policy.recency_half_life_days)
        weight = similarity * recency * source_weight
        if weight == 0:
            evidence["zero_weight_count"] += 1
            continue
        evidence["matched_history_count"] += 1
        if status == "completed" and date_basis == "participation_date":
            evidence["completion_date_proxy_count"] += 1
        outcome = outcomes[status]
        weights.append(weight)
        weighted_outcomes.append(weight * outcome)
        if outcome > policy.neutral_value:
            positive.append(weight)
        elif outcome < policy.neutral_value:
            negative.append(weight)
        if similarity >= policy.recent_similarity_threshold and age_days <= policy.recent_window_days:
            if status == "no_show":
                evidence["recent_similar_no_shows"] += 1
            elif status == "completed":
                evidence["recent_similar_completions"] += 1

        rating, rating_status = _optional_number(record.get("feedback_rating"), 1, 5)
        assessment, assessment_status = _optional_number(record.get("score"), 0, 100)
        for label, observation_status in (("rating", rating_status), ("assessment", assessment_status)):
            if observation_status == "valid":
                evidence[label + "_observation_count"] += 1
            else:
                evidence[observation_status + "_" + label + "_count"] += 1
        rating_signal = (rating - 1) / 4 if rating is not None else None
        assessment_signal = assessment / 100 if assessment is not None else None
        signals = [signal for signal in (rating_signal, assessment_signal) if signal is not None]
        record_signal = fsum(signals) / len(signals) if signals else None
        if record_signal is not None:
            evidence["feedback_record_count"] += 1
            feedback_weights.append(weight)
            weighted_feedback.append(weight * record_signal)
        if include_records:
            record_evidence.append({
                "record_id": record_id, "event_id": event_id, "status": status,
                "skill_similarity": jaccard, "same_type": same_type,
                "same_format": same_format, "similarity": similarity,
                "date_basis": date_basis, "age_days": age_days, "recency": recency,
                "source_weight": source_weight, "source_is_known": known_source,
                "weight": weight, "outcome": outcome,
                "rating_signal": rating_signal, "assessment_signal": assessment_signal,
                "record_feedback_signal": record_signal,
            })
    total_weight = fsum(weights)
    total_feedback_weight = fsum(feedback_weights)
    evidence["effective_history_weight"] = total_weight
    evidence["effective_feedback_weight"] = total_feedback_weight
    evidence["positive_weight"] = fsum(positive)
    evidence["negative_weight"] = fsum(negative)
    evidence["weighted_outcome_sum"] = fsum(weighted_outcomes)
    evidence["weighted_feedback_sum"] = fsum(weighted_feedback)
    compatibility = (policy.prior_weight * policy.neutral_value + evidence["weighted_outcome_sum"]) / (
        policy.prior_weight + total_weight
    )
    feedback_signal = (policy.feedback_prior_weight * policy.feedback_neutral_value + evidence["weighted_feedback_sum"]) / (
        policy.feedback_prior_weight + total_feedback_weight
    )
    result = {
        "compatibility": min(1.0, max(0.0, compatibility)),
        "feedback_signal": min(1.0, max(0.0, feedback_signal)),
        "evidence": evidence,
    }
    if include_records:
        result["record_evidence"] = record_evidence
    return result
