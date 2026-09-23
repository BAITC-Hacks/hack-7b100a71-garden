"""End-to-end Step 1 + Step 2 checks on the complete official catalog."""

import copy
import csv
import json
from pathlib import Path
import unittest

from backend.recommendation.career import build_career_state
from backend.recommendation.contracts import RecommendationInputError
from backend.recommendation.eligibility import evaluate_catalog, evaluate_event


class OfficialEligibilityIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = Path(__file__).resolve().parents[2] / "data" / "career_quest_dataset"
        skills = json.loads((folder / "skills.json").read_text(encoding="utf-8"))
        cls.profiles = skills["role_profiles"]
        cls.snapshot = skills["meta"]["as_of_date"]
        cls.employees = json.loads((folder / "employees.json").read_text(encoding="utf-8"))["employees"]
        cls.events = json.loads((folder / "events.json").read_text(encoding="utf-8"))["events"]
        with (folder / "activity_history.csv").open(encoding="utf-8", newline="") as stream:
            cls.history = list(csv.DictReader(stream))
        cls.original_inputs = copy.deepcopy((cls.employees, cls.profiles, cls.events, cls.history))
        cls.states = {
            e["employee_id"]: build_career_state(e, cls.profiles, cls.events, cls.history, as_of=cls.snapshot)
            for e in cls.employees
        }
        cls.original_states = copy.deepcopy(cls.states)
        cls.results = {
            e["employee_id"]: evaluate_catalog(e, cls.states[e["employee_id"]], cls.profiles, cls.events, cls.history, as_of=cls.snapshot)
            for e in cls.employees
        }

    def test_every_official_candidate_meets_admission_and_has_positive_target_impact(self):
        events = {event["event_id"]: event for event in self.events}
        for employee in self.employees:
            result = self.results[employee["employee_id"]]
            self.assertEqual(result["event_count"], len(events))
            self.assertEqual(result["eligible_count"] + result["rejected_count"], len(events))
            for candidate in result["eligible_candidates"]:
                with self.subTest(employee=employee["employee_id"], event=candidate["event_id"]):
                    event = events[candidate["event_id"]]
                    self.assertFalse(event["mandatory"])
                    self.assertIn(employee["grade"], event["target_grades"])
                    goal = employee["career_goal"]
                    self.assertTrue(employee["role"] in event["target_roles"] or (goal and goal["target_role"] in event["target_roles"]))
                    self.assertTrue(all(p["met"] for p in candidate["evidence"]["prerequisite_checks"]))
                    self.assertTrue(candidate["evidence"]["availability"]["available"])
                    self.assertFalse(candidate["evidence"]["history"]["in_progress_record_ids"])
                    if not candidate["evidence"]["history"]["recurring_exception"]:
                        self.assertFalse(candidate["evidence"]["history"]["completed_record_ids"])
                    self.assertGreater(candidate["simulation"]["total_gap_reduction"], 0)
                    self.assertGreater(candidate["simulation"]["readiness_delta"], 0)
                    self.assertEqual(candidate["rejection_reasons"], [])

    def test_hypothetical_impacts_share_the_unchanged_step1_baseline(self):
        for employee_id, result in self.results.items():
            state = self.states[employee_id]
            for evaluation in result["eligible_candidates"] + result["rejected_events"]:
                if state["target"] is None:
                    self.assertIsNone(evaluation["simulation"])
                    continue
                simulation = evaluation["simulation"]
                self.assertEqual(simulation["skill_gaps_before"], state["skill_gaps"])
                self.assertEqual(simulation["readiness_before_details"], state["career_readiness"])
                self.assertGreaterEqual(simulation["readiness_after"], simulation["readiness_before"])
                self.assertLessEqual(simulation["readiness_after"], 1)
                self.assertEqual(simulation["total_gap_before"] - simulation["total_gap_after"], simulation["total_gap_reduction"])
                self.assertEqual(simulation["critical_gap_before"] - simulation["critical_gap_after"], simulation["critical_gap_reduction"])
        self.assertEqual(self.states, self.original_states)
        self.assertEqual((self.employees, self.profiles, self.events, self.history), self.original_inputs)

    def test_official_promotion_transition_and_empty_results_have_explainable_regressions(self):
        # These are reference outputs, not profile-specific branches in the engine.
        first = self.results["E0001"]
        self.assertEqual([c["event_id"] for c in first["eligible_candidates"]], ["EV_005", "EV_036"])
        transition = self.results["E0004"]
        self.assertEqual([c["event_id"] for c in transition["eligible_candidates"]], ["EV_021", "EV_026", "EV_027"])
        audience = {c["event_id"]: c["evidence"]["audience_match"] for c in transition["eligible_candidates"]}
        self.assertEqual(audience, {"EV_021": "both", "EV_026": "target_role", "EV_027": "target_role"})
        self.assertEqual(self.results["E0018"]["eligible_candidates"], [])
        previous = next(r for r in self.results["E0018"]["rejected_events"] if r["event_id"] == "EV_034")
        self.assertEqual([r["code"] for r in previous["rejection_reasons"]], ["ALREADY_COMPLETED"])
        self.assertGreater(previous["simulation"]["total_gap_reduction"], 0)

    def test_every_no_target_employee_gets_explanations_instead_of_invented_candidates(self):
        for result in self.results.values():
            if result["target"] is not None:
                continue
            self.assertEqual(result["eligible_count"], 0)
            for rejection in result["rejected_events"]:
                codes = {r["code"] for r in rejection["rejection_reasons"]}
                self.assertIn("NO_CAREER_TARGET", codes)
                self.assertNotIn("NO_TARGET_GAP_IMPACT", codes)

    def test_official_outputs_are_json_safe_and_do_not_depend_on_input_order(self):
        for result in self.results.values():
            json.dumps(result, allow_nan=False)
        employee = next(e for e in self.employees if e["employee_id"] == "E0004")
        actual = evaluate_catalog(employee, self.states["E0004"], list(reversed(self.profiles)), list(reversed(self.events)), list(reversed(self.history)), as_of=self.snapshot)
        self.assertEqual(actual, self.results["E0004"])

    def test_invalid_readiness_context_uses_a_structured_boundary_error(self):
        employee = self.employees[0]
        state = copy.deepcopy(self.states[employee["employee_id"]])
        state["career_readiness"] = "not a Step 1 result"
        target = state["target"]
        profile = next(p for p in self.profiles if (p["role"], p["grade"]) == (target["role"], target["grade"]))
        with self.assertRaises(RecommendationInputError):
            evaluate_event(employee, state, profile, self.events[0], self.history, as_of=self.snapshot)


if __name__ == "__main__":
    unittest.main()
