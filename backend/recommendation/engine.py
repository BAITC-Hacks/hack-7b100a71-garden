"""Deterministic recommendations from validated mappings; no I/O, API or LLM."""

from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from math import inf
from typing import List

from .career import build_career_state
from .config import DEFAULT_CONFIG, RecommendationConfig
from .contracts import CalendarDate, RankedRecommendation, RecommendationInputError, RecommendationResult
from .eligibility import evaluate_catalog
from .history import calculate_history_signals
from .scoring import score_candidates


def _ranking_key(recommendation):
    simulation = recommendation["simulation"]
    availability = recommendation["evidence"]["availability"]
    duration = recommendation["scoring_evidence"]["duration_hours"]
    return (
        -recommendation["score"],
        -simulation["critical_gap_reduction"],
        -simulation["total_gap_reduction"],
        0 if availability["self_paced"] else availability["days_until_next_session"],
        duration if duration is not None else inf,
        recommendation["event_id"],
    )


def rank_eligible_candidates(
    employee_id: str,
    candidates: Sequence,
    events: Sequence,
    history: Sequence,
    *,
    as_of: CalendarDate,
    config: RecommendationConfig = DEFAULT_CONFIG,
    include_history_records: bool = False,
) -> List[RankedRecommendation]:
    """Rank the complete Step 2 eligible set, without truncating normalization.

    This lower-level entry point is useful for audits. Call recommend() for a
    fresh career state, admission checks and Top 1–3. History cannot veto a
    candidate. Detailed participation evidence is opt-in for backend debugging.
    """
    if type(include_history_records) is not bool:
        raise RecommendationInputError("invalid_history_detail_option", "include_history_records must be boolean")
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise RecommendationInputError("invalid_candidates", "Supply all Step 2 eligible candidates")
    if not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
        raise RecommendationInputError("invalid_events", "Supply the event catalog sequence")
    event_index = {}
    for event in events:
        if not isinstance(event, Mapping) or not isinstance(event.get("event_id"), str):
            raise RecommendationInputError("invalid_event", "Catalog entries need event_id")
        if event["event_id"] in event_index:
            raise RecommendationInputError("duplicate_event_id", "Catalog event IDs must be unique")
        event_index[event["event_id"]] = event
    signals = {}
    candidate_index = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping) or not isinstance(candidate.get("event_id"), str):
            raise RecommendationInputError("invalid_candidate", "Candidate must include event_id")
        event_id = candidate["event_id"]
        if event_id in candidate_index:
            raise RecommendationInputError("duplicate_candidate_id", "Candidate event IDs must be unique")
        if event_id not in event_index:
            raise RecommendationInputError("unknown_event_id", "Candidate is missing from the catalog")
        if candidate.get("eligible") is not True:
            raise RecommendationInputError("ineligible_candidate", "Only Step 2 eligible candidates may be ranked")
        candidate_index[event_id] = candidate
        signals[event_id] = calculate_history_signals(
            employee_id, event_index[event_id], events, history, as_of=as_of,
            config=config, include_records=include_history_records,
        )
    scored = score_candidates(candidates, events, signals, config=config)
    ranked = []
    for scoring in scored:
        event_id = scoring["event_id"]
        candidate = candidate_index[event_id]
        ranked.append({
            **scoring,
            "title": candidate["title"],
            "simulation": deepcopy(candidate["simulation"]),
            "evidence": deepcopy(candidate["evidence"]),
            "history_signals": signals[event_id],
        })
    ranked.sort(key=_ranking_key)
    for rank, item in enumerate(ranked, 1):
        item["rank"] = rank
    return ranked


def _blocked_summary(state, admission, events):
    event_index = {event["event_id"]: event for event in events}
    counts = Counter()
    blocked = []
    useful = []
    covered_skills = set()
    for rejected in admission["rejected_events"]:
        codes = [reason["code"] for reason in rejected["rejection_reasons"]]
        counts.update(codes)
        blocked.append({"event_id": rejected["event_id"], "rejection_codes": list(codes)})
        simulation = rejected["simulation"]
        if simulation and not event_index[rejected["event_id"]]["mandatory"]:
            covered_skills.update(impact["skill_id"] for impact in simulation["target_skill_impact"]
                                  if impact["useful_gain"] > 0)
            if simulation["total_gap_reduction"] > 0:
                useful.append({
                    "event_id": rejected["event_id"], "rejection_codes": list(codes),
                    "total_gap_reduction": simulation["total_gap_reduction"],
                    "critical_gap_reduction": simulation["critical_gap_reduction"],
                })
    return {
        "rejection_counts": dict(sorted(counts.items())),
        "event_rejections": blocked,
        # Coverage ignores admission; it asks whether the voluntary catalog can
        # increase this missing target skill at all from the current baseline.
        "uncovered_target_gaps": [dict(gap) for gap in state["skill_gaps"] if gap["skill_id"] not in covered_skills],
        "useful_blocked_events": useful,
    }


def recommend(
    employee: Mapping,
    role_profiles: Sequence,
    events: Sequence,
    history: Sequence,
    *,
    as_of: CalendarDate,
    top_n: int = 3,
    config: RecommendationConfig = DEFAULT_CONFIG,
    include_history_records: bool = False,
) -> RecommendationResult:
    """Build fresh state, filter, score all candidates, then return Top 1–3."""
    if type(top_n) is not int or not 1 <= top_n <= 3:
        raise RecommendationInputError("invalid_top_n", "top_n must be an integer from 1 to 3")
    if type(include_history_records) is not bool:
        raise RecommendationInputError("invalid_history_detail_option", "include_history_records must be boolean")
    state = build_career_state(employee, role_profiles, events, history, as_of=as_of, config=config)
    admission = evaluate_catalog(employee, state, role_profiles, events, history, as_of=as_of, config=config)
    ranked = rank_eligible_candidates(
        state["employee_id"], admission["eligible_candidates"], events, history,
        as_of=as_of, config=config, include_history_records=include_history_records,
    )
    status = state["status"]
    if status == "ok" and not ranked:
        status = "no_eligible_recommendations"
    selected = ranked[:top_n]
    return {
        "employee_id": state["employee_id"], "as_of": state["as_of"], "status": status,
        "target": deepcopy(state["target"]),
        "career_readiness": deepcopy(state["career_readiness"]),
        "skill_gaps": deepcopy(state["skill_gaps"]),
        "career_state": state,
        "candidate_count": len(ranked), "recommendation_count": len(selected),
        "recommendations": selected,
        "blocked_summary": _blocked_summary(state, admission, events) if not ranked else None,
    }
