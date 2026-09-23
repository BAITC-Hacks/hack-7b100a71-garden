"""Offline ranking audit; diagnostics never alter the production ranking.

Run from the repository root:
    PYTHONDONTWRITEBYTECODE=1 python3 tests/recommendation/audit_step3.py
"""

import argparse
from collections import Counter
import csv
import hashlib
import json
from math import fsum
from pathlib import Path
from statistics import mean, median
import sys
from time import perf_counter


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.recommendation.config import DEFAULT_CONFIG
from backend.recommendation.eligibility import evaluate_catalog
from backend.recommendation.engine import _ranking_key, rank_eligible_candidates, recommend


# Review thresholds only. These do not participate in scoring or admission.
AUDIT_THRESHOLDS = {
    "material_gap_difference": 2,
    "material_career_score_difference": 0.05,
    "very_low_relevance": 0.25,
    "near_tie_score_difference": 0.01,
    "low_score": 0.25,
    "high_score": 0.95,
    "material_history_top_change_margin": 0.01,
}
CAREER_FACTORS = ("critical_skill_impact", "gap_reduction", "career_relevance")
HISTORY_FACTORS = ("historical_compatibility", "history_feedback_signal")


def load_dataset(folder):
    skills = json.loads((folder / "skills.json").read_text(encoding="utf-8"))
    employees = json.loads((folder / "employees.json").read_text(encoding="utf-8"))["employees"]
    events = json.loads((folder / "events.json").read_text(encoding="utf-8"))["events"]
    with (folder / "activity_history.csv").open(encoding="utf-8", newline="") as stream:
        history = list(csv.DictReader(stream))
    return employees, skills["role_profiles"], events, history, skills["meta"]["as_of_date"]


def partial_score(recommendation, names):
    return fsum(recommendation["factors"][name]["contribution"] for name in names)


def alternative_order(ranked, names):
    return sorted(ranked, key=lambda r: (-partial_score(r, names), *_ranking_key(r)[1:]))


def identifiers(ranked):
    return [r["event_id"] for r in ranked]


def compact(recommendation):
    simulation = recommendation["simulation"]
    return {
        "rank": recommendation["rank"], "event_id": recommendation["event_id"],
        "title": recommendation["title"], "score": recommendation["score"],
        "factors": recommendation["factors"],
        "career_only_score": partial_score(recommendation, CAREER_FACTORS),
        "critical_gap_reduction": simulation["critical_gap_reduction"],
        "total_gap_reduction": simulation["total_gap_reduction"],
        "requirements_closed": simulation["requirements_closed"],
        "critical_requirements_closed": simulation["critical_requirements_closed"],
        "readiness_before": simulation["readiness_before"],
        "readiness_after": simulation["readiness_after"],
        "readiness_delta": simulation["readiness_delta"],
        "audience_match": recommendation["evidence"]["audience_match"],
        "availability": recommendation["evidence"]["availability"],
        "history_evidence": recommendation["history_signals"]["evidence"],
    }


def distribution(values):
    if not values:
        return {"count": 0, "min": None, "median": None, "mean": None, "max": None, "bins": {}}
    bins = Counter()
    for value in values:
        bucket = min(int(value * 10), 9)
        label = "[{:.1f},{:.1f}{}".format(bucket / 10, (bucket + 1) / 10, ")" if bucket < 9 else "]")
        bins[label] += 1
    return {
        "count": len(values), "min": min(values), "median": median(values),
        "mean": mean(values), "max": max(values), "bins": dict(sorted(bins.items())),
    }


def inspect_ranking(employee_id, ranked, no_history_order):
    if not ranked:
        return []
    top = ranked[0]
    simulation = top["simulation"]
    findings = []

    def finding(code, alternatives=()):
        findings.append({"employee_id": employee_id, "code": code, "top": compact(top),
                         "alternatives": [compact(r) for r in alternatives]})

    critical = [r for r in ranked[1:] if r["simulation"]["critical_gap_reduction"] > 0]
    if simulation["critical_gap_reduction"] == 0 and critical:
        finding("ZERO_CRITICAL_WHILE_ALTERNATIVE_HAS_CRITICAL", critical)
    more_gaps = [r for r in ranked[1:] if r["simulation"]["total_gap_reduction"] - simulation["total_gap_reduction"] >= AUDIT_THRESHOLDS["material_gap_difference"]]
    if more_gaps:
        finding("MATERIALLY_SMALLER_GAP_REDUCTION", more_gaps)
    previous_top = no_history_order[0]
    if (previous_top["event_id"] != top["event_id"]
            and previous_top["history_signals"]["compatibility"] < DEFAULT_CONFIG.history.neutral_value
            and partial_score(previous_top, CAREER_FACTORS) - partial_score(top, CAREER_FACTORS) >= AUDIT_THRESHOLDS["material_career_score_difference"]):
        finding("NEGATIVE_HISTORY_OVERTAKES_MATERIAL_CAREER_ADVANTAGE", [previous_top])
    low_relevance = [r for r in ranked[:3] if r["factors"]["career_relevance"]["normalized"] < AUDIT_THRESHOLDS["very_low_relevance"]]
    if low_relevance:
        finding("VERY_LOW_RELEVANCE_IN_TOP3", low_relevance)
    if len(ranked) > 1 and top["score"] - ranked[1]["score"] < AUDIT_THRESHOLDS["near_tie_score_difference"]:
        finding("NEAR_TIE_FOR_TOP1", [ranked[1]])
    if top["score"] < AUDIT_THRESHOLDS["low_score"]:
        finding("LOW_TOP1_SCORE")
    if top["score"] > AUDIT_THRESHOLDS["high_score"]:
        finding("HIGH_TOP1_SCORE")
    return findings


def audit(folder):
    employees, profiles, events, history, snapshot = load_dataset(folder)
    employees = sorted(employees, key=lambda e: e["employee_id"])
    outputs = {}
    all_started = perf_counter()
    for employee in employees:
        outputs[employee["employee_id"]] = recommend(employee, profiles, events, history, as_of=snapshot)
    all_ms = (perf_counter() - all_started) * 1000
    first = employees[0]
    individual_ms = []
    for _ in range(20):
        start = perf_counter()
        recommend(first, profiles, events, history, as_of=snapshot)
        individual_ms.append((perf_counter() - start) * 1000)
    factor_names = tuple(vars(DEFAULT_CONFIG.scoring_weights))
    nonhistory_names = tuple(name for name in factor_names if name not in HISTORY_FACTORS)
    employee_summaries = []
    diagnostics = []
    changes = Counter()
    history_changed_profiles = []
    material_history_profiles = []
    top1 = []
    returned = []
    for employee in employees:
        key = employee["employee_id"]
        output = outputs[key]
        admission = evaluate_catalog(employee, output["career_state"], profiles, events, history, as_of=snapshot)
        ranked = rank_eligible_candidates(key, admission["eligible_candidates"], events, history, as_of=snapshot)
        assert ranked[:3] == output["recommendations"]
        career_order = alternative_order(ranked, CAREER_FACTORS)
        no_history_order = alternative_order(ranked, nonhistory_names)
        career_plus_history_order = alternative_order(ranked, CAREER_FACTORS + HISTORY_FACTORS)
        for name, order in (("full_vs_career_only", career_order), ("isolated_history_effect", no_history_order)):
            if identifiers(order) != identifiers(ranked):
                changes[name + "_ordering_changed"] += 1
            if ranked and order[0]["event_id"] != ranked[0]["event_id"]:
                changes[name + "_top1_changed"] += 1
        if identifiers(career_plus_history_order) != identifiers(career_order):
            changes["career_plus_history_vs_career_only_ordering_changed"] += 1
        if ranked and career_plus_history_order[0]["event_id"] != career_order[0]["event_id"]:
            changes["career_plus_history_vs_career_only_top1_changed"] += 1
        if ranked and ranked[0]["event_id"] != no_history_order[0]["event_id"]:
            history_changed_profiles.append(key)
            if ranked[0]["score"] - no_history_order[0]["score"] >= AUDIT_THRESHOLDS["material_history_top_change_margin"]:
                material_history_profiles.append(key)
        diagnostics.extend(inspect_ranking(key, ranked, no_history_order))
        if ranked:
            top1.append((employee, ranked[0]))
        returned.extend(output["recommendations"])
        employee_summaries.append({
            "employee_id": key, "current_role": employee["role"], "current_grade": employee["grade"],
            "target": output["target"], "status": output["status"],
            "candidate_count": output["candidate_count"], "recommendation_count": output["recommendation_count"],
            "full_order": identifiers(ranked), "career_only_order": identifiers(career_order),
            "no_history_order": identifiers(no_history_order),
            "career_plus_history_order": identifiers(career_plus_history_order),
            "all_ranked_candidates": [compact(r) for r in ranked],
            "blocked_summary": output["blocked_summary"],
        })
    representative_ids = [key for key in ("E0001", "E0002", "E0004", "E0014", "E0018", "E0006") if key in outputs]
    if material_history_profiles or history_changed_profiles:
        representative_ids.append((material_history_profiles or history_changed_profiles)[0])
    only_one = next((e["employee_id"] for e in employee_summaries if e["candidate_count"] == 1), None)
    if only_one:
        representative_ids.append(only_one)
    finding_counts = Counter(f["code"] for f in diagnostics)
    all_finding_codes = (
        "ZERO_CRITICAL_WHILE_ALTERNATIVE_HAS_CRITICAL", "MATERIALLY_SMALLER_GAP_REDUCTION",
        "NEGATIVE_HISTORY_OVERTAKES_MATERIAL_CAREER_ADVANTAGE", "VERY_LOW_RELEVANCE_IN_TOP3",
        "NEAR_TIE_FOR_TOP1", "LOW_TOP1_SCORE", "HIGH_TOP1_SCORE",
    )
    return {
        "as_of": snapshot,
        "dataset_sha256": {name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
                           for name in ("skills.json", "employees.json", "events.json", "activity_history.csv")},
        "comparison_policy": {
            "career_only": "0.35*C + 0.25*G + 0.15*R, no rescaling; same production tie-breaks",
            "full_vs_career_only": "Includes both H/F and E/A effects; must not attribute every change to history",
            "isolated_history_effect": "Full ranking compared with C/G/R/E/A only; same normalization and tie-breaks",
            "career_plus_history_vs_career_only": "C/G/R/H/F compared with C/G/R; omits E/A on both sides",
        },
        "audit_thresholds": AUDIT_THRESHOLDS,
        "summary": {
            "employees": len(employees),
            "employees_with_recommendations": len(top1),
            "employees_without_recommendations": len(employees) - len(top1),
            "total_recommendations_returned": len(returned),
            "status_counts": dict(sorted(Counter(r["status"] for r in outputs.values()).items())),
            "total_candidates": sum(r["candidate_count"] for r in outputs.values()),
            "average_candidate_count_all_employees": mean(r["candidate_count"] for r in outputs.values()),
            "top1_events_frequency": dict(sorted(Counter(r["event_id"] for _, r in top1).items())),
            "top1_score_distribution": distribution([r["score"] for _, r in top1]),
            "returned_score_distribution": distribution([r["score"] for r in returned]),
            "top1_factor_averages": {name: mean(r["factors"][name]["normalized"] for _, r in top1) if top1 else None for name in factor_names},
            "top1_addressing_critical_gaps": sum(r["simulation"]["critical_gap_reduction"] > 0 for _, r in top1),
            "top1_closing_requirement": sum(bool(r["simulation"]["requirements_closed"]) for _, r in top1),
            "cross_role_top1_admitted_via_target_role": sum(e["role"] != r["evidence"]["target_role"] and r["evidence"]["audience_match"] == "target_role" for e, r in top1),
            "ordering_comparisons": {key: changes[key] for key in (
                "full_vs_career_only_ordering_changed", "full_vs_career_only_top1_changed",
                "isolated_history_effect_ordering_changed", "isolated_history_effect_top1_changed",
                "career_plus_history_vs_career_only_ordering_changed", "career_plus_history_vs_career_only_top1_changed",
            )},
            "history_changed_top1_profile_ids": history_changed_profiles,
            "material_history_changed_top1_profile_ids": material_history_profiles,
            "suspicious_case_counts": {code: finding_counts[code] for code in all_finding_codes},
        },
        "performance": {
            "scope": "Plain Python computation, preloaded mappings, no dataset I/O or network in timers",
            "one_employee_id": first["employee_id"], "one_employee_repeats": len(individual_ms),
            "one_employee_median_ms": median(individual_ms), "one_employee_max_ms": max(individual_ms),
            "all_employees_ms": all_ms, "ui_api_target_ms": 2000,
        },
        "employees": employee_summaries,
        "suspicious_cases": diagnostics,
        "representatives": {key: outputs[key] for key in dict.fromkeys(representative_ids)},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "career_quest_dataset")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "step3-results.json")
    args = parser.parse_args()
    report = audit(args.dataset)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"summary": report["summary"], "performance": report["performance"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
