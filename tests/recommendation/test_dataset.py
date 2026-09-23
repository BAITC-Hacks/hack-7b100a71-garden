"""Official-data integration and independent new-role boundary fixtures."""

import copy
import csv
import json
from pathlib import Path
import unittest

from backend.recommendation.career import build_career_state
from backend.recommendation.contracts import RecommendationInputError


class OfficialDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = Path(__file__).resolve().parents[2] / "data" / "career_quest_dataset"
        skills = json.loads((folder / "skills.json").read_text(encoding="utf-8"))
        cls.employees = json.loads((folder / "employees.json").read_text(encoding="utf-8"))["employees"]
        cls.events = json.loads((folder / "events.json").read_text(encoding="utf-8"))["events"]
        cls.profiles = skills["role_profiles"]
        cls.snapshot = skills["meta"]["as_of_date"]
        with (folder / "activity_history.csv").open(encoding="utf-8", newline="") as stream:
            cls.history = list(csv.DictReader(stream))
        cls.originals = copy.deepcopy((cls.employees, cls.events, cls.profiles, cls.history))
        cls.states = [build_career_state(e, cls.profiles, cls.events, cls.history, as_of=cls.snapshot) for e in cls.employees]

    def test_every_employee_serializes_and_preserves_the_review_baseline(self):
        for employee, state in zip(self.employees, self.states):
            with self.subTest(employee=employee["employee_id"]):
                self.assertEqual(state["employee_id"], employee["employee_id"])
                self.assertEqual(state["as_of"], self.snapshot)
                json.dumps(state, allow_nan=False)
                effective = state["skills_reconstruction"]["effective_skills"]
                for skill, level in employee["skills"].items():
                    self.assertGreaterEqual(effective[skill], level)
                self.assertTrue(all(0 <= level <= 5 for level in effective.values()))
        self.assertEqual((self.employees, self.events, self.profiles, self.history), self.originals)

    def test_targets_and_readiness_follow_each_employees_actual_goal(self):
        profile_index = {(p["role"], p["grade"]): p for p in self.profiles}
        grade_order = ("Junior", "Middle", "Senior", "Lead")
        for employee, state in zip(self.employees, self.states):
            with self.subTest(employee=employee["employee_id"]):
                goal = employee["career_goal"]
                if goal is None and employee["grade"] == "Lead":
                    self.assertEqual(state["status"], "no_next_grade")
                    self.assertIsNone(state["target"])
                    self.assertIsNone(state["career_readiness"])
                    self.assertEqual(state["skill_gaps"], [])
                    continue
                expected = (goal["target_role"], goal["target_grade"]) if goal else (
                    employee["role"], grade_order[grade_order.index(employee["grade"]) + 1])
                target = state["target"]
                self.assertEqual((target["role"], target["grade"]), expected)
                readiness = state["career_readiness"]
                self.assertTrue(0 <= readiness["current"] <= 1)
                self.assertEqual(readiness["all_requirements_met"], not state["skill_gaps"])
                target_critical = set(profile_index[expected]["critical_skills"])
                critical_gaps = [gap for gap in state["skill_gaps"] if gap["skill_id"] in target_critical]
                self.assertEqual(readiness["remaining_critical_gaps"], critical_gaps)
                self.assertEqual(readiness["critical_requirements_met"], not critical_gaps)

    def test_reordered_official_input_is_deterministic(self):
        # Select by profile features rather than embedding employee-specific logic.
        sample = next(e for e in self.employees if e["career_goal"] and e["career_goal"]["target_role"] != e["role"])
        expected = next(s for s in self.states if s["employee_id"] == sample["employee_id"])
        actual = build_career_state(sample, list(reversed(self.profiles)), list(reversed(self.events)), list(reversed(self.history)), as_of=self.snapshot)
        self.assertEqual(actual, expected)


class UnseenProfileIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.employee = {
            "employee_id": "jury-new-person", "role": "Research Engineer", "grade": "Middle",
            "career_goal": {"target_role": "Service Designer", "target_grade": "Middle"},
            "skills": {"RESEARCH": 5}, "last_review_date": "2026-09-01",
        }
        self.profiles = [
            {"role": "Research Engineer", "grade": "Middle", "required_skills": {"RESEARCH": 2}, "critical_skills": ["RESEARCH"]},
            {"role": "Service Designer", "grade": "Middle", "required_skills": {"DESIGN": 2, "COMMUNICATION": 2}, "critical_skills": ["DESIGN"]},
        ]
        self.events = [{"event_id": "jury-new-event", "format": "online", "develops_skills": [{"skill_id": "DESIGN", "gain": 2, "max_level": 4}]}]
        self.history = [{"record_id": "jury-new-record", "employee_id": "jury-new-person", "event_id": "jury-new-event", "date": "2026-09-12", "status": "completed", "completed_at": "2026-09-13T12:00:00+06:00"}]

    def test_unseen_role_skill_event_and_employee_ids_work_without_special_cases(self):
        state = build_career_state(self.employee, self.profiles, self.events, self.history, as_of="2026-10-01")
        self.assertEqual(state["status"], "ok")
        self.assertEqual(state["target"], {"role": "Service Designer", "grade": "Middle", "source": "career_goal"})
        self.assertEqual(state["skills_reconstruction"]["effective_skills"]["DESIGN"], 2)
        self.assertEqual(state["career_readiness"]["current"], 4 / 6)
        self.assertTrue(state["career_readiness"]["critical_requirements_met"])
        self.assertFalse(state["career_readiness"]["all_requirements_met"])
        self.assertEqual(state["skill_gaps"], [{"skill_id": "COMMUNICATION", "current": 0, "required": 2, "gap": 2, "critical": False}])

    def test_snapshot_is_explicit_and_review_cannot_be_in_future(self):
        with self.assertRaises(TypeError):
            build_career_state(self.employee, self.profiles, self.events, self.history)
        with self.assertRaises(RecommendationInputError):
            build_career_state(self.employee, self.profiles, self.events, self.history, as_of="2026-08-01")

    def test_empty_target_requirements_are_not_reported_as_full_readiness(self):
        self.profiles[1]["required_skills"] = {}
        self.profiles[1]["critical_skills"] = []
        state = build_career_state(self.employee, self.profiles, self.events, self.history, as_of="2026-10-01")
        self.assertEqual(state["status"], "invalid_target_requirements")
        self.assertIsNone(state["career_readiness"]["current"])
        self.assertIsNone(state["career_readiness"]["all_requirements_met"])

    def test_full_reconstructed_coverage_returns_target_satisfied(self):
        self.employee["skills"]["COMMUNICATION"] = 2
        state = build_career_state(self.employee, self.profiles, self.events, self.history, as_of="2026-10-01")
        self.assertEqual(state["status"], "target_satisfied")
        self.assertEqual(state["career_readiness"]["current"], 1.0)
        self.assertEqual(state["skill_gaps"], [])

    def test_invalid_employee_uses_the_structured_boundary_error(self):
        with self.assertRaises(RecommendationInputError):
            build_career_state(None, self.profiles, self.events, self.history, as_of="2026-10-01")


if __name__ == "__main__":
    unittest.main()
