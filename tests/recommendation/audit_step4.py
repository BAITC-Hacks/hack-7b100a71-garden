"""Offline explanation demonstration; never reads a key or calls the network.

Run from the repository root:
    PYTHONDONTWRITEBYTECODE=1 python3 tests/recommendation/audit_step4.py
"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from audit_step3 import load_dataset
from backend.ai.config import SUPPORTED_LANGUAGES
from backend.ai.explanations import enrich_recommendations
from backend.recommendation.engine import recommend


def engine_fields(enriched):
    original = deepcopy(enriched)
    original.pop("explanation_summary", None)
    original.pop("explanation_meta", None)
    for item in original["recommendations"]:
        item.pop("explanation", None)
    return original


def offline_coaching_transport(payload, **kwargs):
    """Test double: not an OpenAI response obtained from the network."""
    request = json.loads(payload["input"][0]["content"])
    choices = {"language": request["language"], "explanations": [{
        "event_id": event["event_id"],
        "fact_variants": [{"fact_id": fact["fact_id"], "variant": "coaching"} for fact in event["facts"]],
    } for event in request["recommendations"]]}
    return {"status": "completed", "output": [{
        "type": "message", "role": "assistant", "status": "completed",
        "content": [{"type": "output_text", "text": json.dumps(choices)}],
    }]}


def compact(result):
    return {
        "employee_id": result["employee_id"], "target": result["target"], "status": result["status"],
        "candidate_count": result["candidate_count"], "recommendation_count": result["recommendation_count"],
        "explanation_meta": result["explanation_meta"], "explanation_summary": result["explanation_summary"],
        "recommendations": [{name: item[name] for name in ("rank", "event_id", "title", "score", "explanation")}
                            for item in result["recommendations"]],
    }


def audit(folder):
    employees, profiles, events, history, snapshot = load_dataset(folder)
    demos = {}
    verified = 0
    explanation_count = 0
    times_ms = []
    mock_successes = 0
    for employee in employees:
        original = recommend(employee, profiles, events, history, as_of=snapshot)
        before = deepcopy(original)
        localized = {}
        for language in SUPPORTED_LANGUAGES:
            start = perf_counter()
            # Force the missing-key path even if a real key exists on the host.
            result = enrich_recommendations(original, preferred_language=language, use_openai=True, environ={})
            times_ms.append((perf_counter() - start) * 1000)
            assert engine_fields(result) == before
            assert original == before
            assert result["explanation_meta"]["provider_status"] == ("missing_api_key" if original["recommendations"] else "no_recommendations")
            json.dumps(result, ensure_ascii=False, allow_nan=False)
            verified += 1
            explanation_count += result["recommendation_count"]
            if employee["employee_id"] in ("E0001", "E0004", "E0002", "E0018"):
                localized[language] = compact(result)
        # Exercise accepted provider choices for every profile using a test double.
        enriched = enrich_recommendations(
            original, preferred_language=employee.get("preferred_language", "ru"),
            use_openai=True, environ={"OPENAI_API_KEY": "offline-test-placeholder"},
            transport=offline_coaching_transport,
        )
        assert engine_fields(enriched) == before
        assert original == before
        if original["recommendations"]:
            assert enriched["explanation_meta"]["provider_status"] == "used"
            mock_successes += 1
        if localized:
            demos[employee["employee_id"]] = {
                "preferred_language": employee.get("preferred_language"),
                "deterministic": localized,
                "provider_test_double": compact(enriched),
            }
    return {
        "as_of": snapshot,
        "notes": [
            "No real API request was made. All provider-success examples use an explicit local test double.",
            "The optional model chooses only approved local wording variants for fixed facts, not free-form claims.",
            "Every engine field is unchanged after enrichment in every tested language and provider-success case.",
        ],
        "summary": {
            "employees": len(employees), "languages": list(SUPPORTED_LANGUAGES),
            "localized_cases_preserving_every_engine_field": verified,
            "localized_recommendation_explanations": explanation_count,
            "provider_test_double_successful_profiles": mock_successes,
            "no_recommendation_profiles": len(employees) - mock_successes,
            "live_api_calls": 0,
        },
        "local_explanation_timing": {
            "scope": "Missing-key fallback only; excludes recommendation computation and data loading",
            "median_ms": median(times_ms), "max_ms": max(times_ms),
        },
        "dataset_sha256": {name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
                           for name in ("skills.json", "employees.json", "events.json", "activity_history.csv")},
        "demonstrations": demos,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "career_quest_dataset")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "step4-results.json")
    args = parser.parse_args()
    report = audit(args.dataset)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"summary": report["summary"], "local_explanation_timing": report["local_explanation_timing"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
