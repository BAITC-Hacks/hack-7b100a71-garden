"""Complete official dataset checks for the Step 3 facade and evidence."""

from copy import deepcopy
import json
from math import fsum
from pathlib import Path
import unittest

from audit_step3 import load_dataset
from backend.recommendation.career import calculate_readiness
from backend.recommendation.engine import recommend


class OfficialRankingIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = Path(__file__).resolve().parents[2] / "data" / "career_quest_dataset"
        cls.employees, cls.profiles, cls.events, cls.history, cls.snapshot = load_dataset(folder)
        cls.before = deepcopy((cls.employees, cls.profiles, cls.events, cls.history))
        cls.results = {e["employee_id"]: recommend(e, cls.profiles, cls.events, cls.history, as_of=cls.snapshot)
                       for e in cls.employees}

    def test_all_official_outputs_keep_step2_population_and_return_real_top3_only(self):
        self.assertEqual(sum(r["candidate_count"] for r in self.results.values()), 503)
        self.assertEqual(sum(r["recommendation_count"] for r in self.results.values()), 388)
        self.assertEqual(sum(r["status"] == "ok" for r in self.results.values()), 163)
        self.assertEqual(sum(r["status"] == "no_eligible_recommendations" for r in self.results.values()), 27)
        self.assertEqual(sum(r["status"] == "no_next_grade" for r in self.results.values()), 10)
        for result in self.results.values():
            self.assertEqual(result["recommendation_count"], min(3, result["candidate_count"]))
            self.assertEqual([r["rank"] for r in result["recommendations"]], list(range(1, result["recommendation_count"] + 1)))

    def test_all_recommendations_expose_reproducible_factors_and_smoothed_history(self):
        for result in self.results.values():
            for item in result["recommendations"]:
                with self.subTest(employee=result["employee_id"], event=item["event_id"]):
                    self.assertEqual(item["score"], fsum(f["contribution"] for f in item["factors"].values()))
                    for factor in item["factors"].values():
                        self.assertGreaterEqual(factor["normalized"], 0)
                        self.assertLessEqual(factor["normalized"], 1)
                        self.assertEqual(factor["contribution"], factor["normalized"] * factor["weight"])
                    signals = item["history_signals"]
                    evidence = signals["evidence"]
                    priors = evidence["priors"]
                    self.assertEqual(signals["compatibility"], (
                        priors["compatibility_weight"] * priors["compatibility_value"] + evidence["weighted_outcome_sum"]
                    ) / (priors["compatibility_weight"] + evidence["effective_history_weight"]))
                    self.assertEqual(signals["feedback_signal"], (
                        priors["feedback_weight"] * priors["feedback_value"] + evidence["weighted_feedback_sum"]
                    ) / (priors["feedback_weight"] + evidence["effective_feedback_weight"]))
                    self.assertNotIn("record_evidence", signals)
                    self.assertEqual(item["scoring_evidence"]["normalization_candidate_count"], result["candidate_count"])

    def test_readiness_and_skill_impact_are_the_unchanged_step1_step2_math(self):
        profiles = {(p["role"], p["grade"]): p for p in self.profiles}
        for result in self.results.values():
            for item in result["recommendations"]:
                simulation = item["simulation"]
                self.assertEqual(simulation["readiness_before_details"], result["career_readiness"])
                profile = profiles[(result["target"]["role"], result["target"]["grade"])]
                self.assertEqual(simulation["readiness_after_details"], calculate_readiness(simulation["simulated_skills_after"], profile))
                self.assertGreater(simulation["total_gap_reduction"], 0)
                self.assertGreater(simulation["readiness_delta"], 0)

    def test_every_empty_result_has_explicit_diagnostics_and_no_invented_rank(self):
        for result in self.results.values():
            if result["recommendations"]:
                self.assertIsNone(result["blocked_summary"])
                continue
            blocked = result["blocked_summary"]
            self.assertEqual(len(blocked["event_rejections"]), len(self.events))
            if result["target"] is None:
                self.assertEqual(result["status"], "no_next_grade")
                self.assertEqual(blocked["rejection_counts"]["NO_CAREER_TARGET"], 40)
            else:
                self.assertTrue(blocked["useful_blocked_events"])
                self.assertTrue(any(e["rejection_codes"] == ["ALREADY_COMPLETED"] for e in blocked["useful_blocked_events"]))

    def test_official_topn_order_immutability_and_json_safety(self):
        for result in self.results.values():
            json.dumps(result, allow_nan=False)
        employee = next(e for e in self.employees if e["employee_id"] == "E0004")
        result = recommend(employee, list(reversed(self.profiles)), list(reversed(self.events)), list(reversed(self.history)), as_of=self.snapshot, top_n=1)
        self.assertEqual(result["recommendations"], self.results["E0004"]["recommendations"][:1])
        self.assertEqual(result["candidate_count"], 3)
        self.assertEqual((self.employees, self.profiles, self.events, self.history), self.before)


if __name__ == "__main__":
    unittest.main()
