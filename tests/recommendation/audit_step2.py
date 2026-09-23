"""Reproducible offline audit, outside the backend's application data layer.

Run from the repository root:
    PYTHONDONTWRITEBYTECODE=1 python3 tests/recommendation/audit_step2.py
"""

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.recommendation.career import build_career_state
from backend.recommendation.eligibility import evaluate_catalog


REASONS = (
    "MANDATORY", "ROLE_MISMATCH", "GRADE_MISMATCH", "PREREQUISITE_NOT_MET",
    "ALREADY_COMPLETED", "ALREADY_IN_PROGRESS", "NO_TARGET_GAP_IMPACT",
    "NO_UPCOMING_SESSION", "NO_CAREER_TARGET",
)
REPRESENTATIVES = {
    "E0001": ("same_role_promotion", ["EV_006", "EV_008", "EV_040"]),
    "E0004": ("cross_role_transition", ["EV_025", "EV_040"]),
    "E0002": ("unmet_prerequisite", ["EV_006", "EV_007", "EV_008"]),
    "E0018": ("completed_activities_no_candidates", ["EV_033", "EV_034", "EV_035", "EV_037", "EV_039", "EV_040"]),
    "E0014": ("lead_with_transition_goal", ["EV_021", "EV_026", "EV_027"]),
    "E0006": ("lead_without_goal", ["EV_005", "EV_037"]),
}


def codes(decision):
    return [reason["code"] for reason in decision["rejection_reasons"]]


def summarize_employee(employee, state, result):
    readiness = state["career_readiness"]
    return {
        "employee_id": employee["employee_id"], "current_role": employee["role"],
        "current_grade": employee["grade"], "target": state["target"],
        "readiness": readiness["current"] if readiness else None,
        "eligible_count": result["eligible_count"],
        "eligible_event_ids": [c["event_id"] for c in result["eligible_candidates"]],
        "rejection_occurrences": dict(sorted(Counter(
            code for rejected in result["rejected_events"] for code in codes(rejected)
        ).items())),
    }


def explain_zero(employee, state, result, event_index):
    explanation = summarize_employee(employee, state, result)
    useful = [r for r in result["rejected_events"]
              if not event_index[r["event_id"]]["mandatory"]
              and r["simulation"] and r["simulation"]["total_gap_reduction"] > 0]
    coverable = {impact["skill_id"] for r in useful
                 for impact in r["simulation"]["target_skill_impact"]
                 if impact["useful_gain"] > 0}
    explanation.update({
        "useful_voluntary_count_ignoring_admission": len(useful),
        "uncovered_gaps_ignoring_admission": [gap for gap in state["skill_gaps"]
                                            if gap["skill_id"] not in coverable],
        "useful_voluntary_rejections": [{
            "event_id": r["event_id"], "rejection_codes": codes(r),
            "total_gap_reduction": r["simulation"]["total_gap_reduction"],
            "critical_gap_reduction": r["simulation"]["critical_gap_reduction"],
            "unmet_prerequisites": [p for p in r["evidence"]["prerequisite_checks"] if not p["met"]],
            "completed_record_ids": r["evidence"]["history"]["completed_record_ids"],
        } for r in useful],
    })
    return explanation


def audit(dataset):
    skills = json.loads((dataset / "skills.json").read_text(encoding="utf-8"))
    employees = json.loads((dataset / "employees.json").read_text(encoding="utf-8"))["employees"]
    events = json.loads((dataset / "events.json").read_text(encoding="utf-8"))["events"]
    with (dataset / "activity_history.csv").open(encoding="utf-8", newline="") as stream:
        history = list(csv.DictReader(stream))
    snapshot = skills["meta"]["as_of_date"]
    event_index = {event["event_id"]: event for event in events}
    states, results = {}, {}
    for employee in sorted(employees, key=lambda e: e["employee_id"]):
        key = employee["employee_id"]
        states[key] = build_career_state(employee, skills["role_profiles"], events, history, as_of=snapshot)
        results[key] = evaluate_catalog(employee, states[key], skills["role_profiles"], events, history, as_of=snapshot)
    candidates = [c for result in results.values() for c in result["eligible_candidates"]]
    rejected = [r for result in results.values() for r in result["rejected_events"]]
    rejections = Counter(code for r in rejected for code in codes(r))
    zero = [explain_zero(e, states[e["employee_id"]], results[e["employee_id"]], event_index)
            for e in employees if not results[e["employee_id"]]["eligible_count"]]
    zero_with_target = [e for e in zero if e["target"] is not None]
    representative_outputs = {}
    for employee in employees:
        key = employee["employee_id"]
        if key not in REPRESENTATIVES:
            continue
        scenario, rejected_ids = REPRESENTATIVES[key]
        result, state = results[key], states[key]
        representative_outputs[key] = {
            "scenario": scenario, "current_role": employee["role"],
            "current_grade": employee["grade"], "career_state": state,
            "eligible_candidates": result["eligible_candidates"],
            "important_rejected_alternatives": [r for r in result["rejected_events"] if r["event_id"] in rejected_ids],
        }
    return {
        "as_of": snapshot,
        "notes": [
            "Candidate counts are employee-event pairs, not unique catalog events or a ranking.",
            "Rejection counts overlap because each decision can have multiple reasons.",
            "Each simulation starts from the same Step 1 state; rejected-event impact is hypothetical only.",
            "Catalog coverage diagnostics ignore admission, but retain gain/max_level and target-requirement caps.",
        ],
        "dataset_sha256": {name: hashlib.sha256((dataset / name).read_bytes()).hexdigest()
                           for name in ("skills.json", "employees.json", "events.json", "activity_history.csv")},
        "summary": {
            "employees": len(employees), "catalog_events": len(events), "history_rows": len(history),
            "employees_with_target": sum(s["target"] is not None for s in states.values()),
            "employees_with_candidates": len(employees) - len(zero),
            "employees_without_candidates": len(zero),
            "employees_without_candidates_with_target": len(zero_with_target),
            "employees_without_candidates_without_target": len(zero) - len(zero_with_target),
            "evaluations": len(candidates) + len(rejected),
            "eligible_pairs": len(candidates), "rejected_pairs": len(rejected),
            "candidate_count_distribution": dict(sorted(Counter(r["eligible_count"] for r in results.values()).items())),
            "rejection_occurrences": {code: rejections[code] for code in REASONS},
            "audience_match_counts": dict(sorted(Counter(c["evidence"]["audience_match"] for c in candidates).items())),
            "candidates_reducing_critical_gaps": sum(c["simulation"]["critical_gap_reduction"] > 0 for c in candidates),
            "candidates_closing_requirements": sum(bool(c["simulation"]["requirements_closed"]) for c in candidates),
            "candidates_closing_critical_requirements": sum(bool(c["simulation"]["critical_requirements_closed"]) for c in candidates),
            "zero_target_profiles_without_any_useful_voluntary_catalog_event": sum(not e["useful_voluntary_count_ignoring_admission"] for e in zero_with_target),
            "zero_target_profiles_with_uncovered_gaps": sum(bool(e["uncovered_gaps_ignoring_admission"]) for e in zero_with_target),
            "zero_target_profiles_with_event_blocked_only_by_completion": sum(any(
                r["rejection_codes"] == ["ALREADY_COMPLETED"] for r in e["useful_voluntary_rejections"]
            ) for e in zero_with_target),
            "zero_target_profiles_with_event_blocked_only_by_prerequisite": sum(any(
                r["rejection_codes"] == ["PREREQUISITE_NOT_MET"] for r in e["useful_voluntary_rejections"]
            ) for e in zero_with_target),
        },
        "employees": [summarize_employee(e, states[e["employee_id"]], results[e["employee_id"]]) for e in employees],
        "zero_candidate_diagnostics": zero,
        "representatives": representative_outputs,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "career_quest_dataset")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "step2-results.json")
    args = parser.parse_args()
    report = audit(args.dataset)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
