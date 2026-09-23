"""Official-data explanation checks, with no live credentials or network."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from audit_step3 import load_dataset
from audit_step4 import engine_fields, offline_coaching_transport
from backend.ai.explanations import enrich_recommendations
from backend.recommendation.engine import recommend


class OfficialExplanationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.employees, profiles, events, history, snapshot = load_dataset(
            Path(__file__).resolve().parents[2] / "data" / "career_quest_dataset",
        )
        cls.results = {employee["employee_id"]: recommend(employee, profiles, events, history, as_of=snapshot)
                       for employee in cls.employees}

    def test_all_200_profiles_in_all_languages_preserve_every_decision(self):
        count = 0
        for original in self.results.values():
            before = deepcopy(original)
            for language in ("kk", "ru", "en"):
                result = enrich_recommendations(original, preferred_language=language, use_openai=True, environ={})
                self.assertEqual(engine_fields(result), before)
                self.assertEqual(original, before)
                self.assertEqual(result["explanation_meta"]["language"], language)
                for item in result["recommendations"]:
                    self.assertEqual(item["explanation"]["source"], "deterministic")
                    self.assertTrue(item["explanation"]["text"])
                self.assertTrue(result["explanation_summary"]["text"])
                json.dumps(result, allow_nan=False)
                count += result["recommendation_count"]
        self.assertEqual(count, 388 * 3)

    def test_successful_provider_wording_preserves_rank_scores_and_all_raw_evidence(self):
        successes = 0
        for employee in self.employees:
            original = self.results[employee["employee_id"]]
            result = enrich_recommendations(
                original, preferred_language=employee["preferred_language"], use_openai=True,
                environ={"OPENAI_API_KEY": "offline-test-placeholder"}, transport=offline_coaching_transport,
            )
            self.assertEqual(engine_fields(result), original)
            if original["recommendations"]:
                self.assertEqual(result["explanation_meta"]["provider_status"], "used")
                successes += 1
            else:
                self.assertEqual(result["explanation_meta"]["provider_status"], "no_recommendations")
        self.assertEqual(successes, 163)

    def test_every_fact_path_resolves_in_the_original_engine_result(self):
        for original in self.results.values():
            result = enrich_recommendations(original, environ={})
            explanations = [result["explanation_summary"]] + [r["explanation"] for r in result["recommendations"]]
            for explanation in explanations:
                for fact in explanation["facts"]:
                    for path in fact["evidence_paths"]:
                        node = original
                        for component in path.split("/")[1:]:
                            node = node[int(component)] if isinstance(node, list) else node[component]

    def test_required_demo_profiles_keep_expected_selection_and_distinct_empty_state(self):
        expected = {"E0001": ["EV_005", "EV_036"], "E0004": ["EV_026", "EV_021", "EV_027"],
                    "E0002": ["EV_005", "EV_036", "EV_011"], "E0018": []}
        for employee_id, events in expected.items():
            result = enrich_recommendations(self.results[employee_id], use_openai=True, environ={})
            self.assertEqual([r["event_id"] for r in result["recommendations"]], events)
        blocked = enrich_recommendations(self.results["E0018"], environ={})
        lead = enrich_recommendations(self.results["E0006"], environ={})
        self.assertEqual(blocked["status"], "no_eligible_recommendations")
        self.assertEqual(lead["status"], "no_next_grade")
        self.assertNotEqual(blocked["explanation_summary"]["text"], lead["explanation_summary"]["text"])


if __name__ == "__main__":
    unittest.main()
