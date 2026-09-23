"""Career target and coverage behavior at the recommendation boundary."""

from copy import deepcopy
from dataclasses import replace
import unittest

from backend.recommendation.career import (
    calculate_readiness,
    calculate_skill_gaps,
    resolve_target,
)
from backend.recommendation.config import DEFAULT_CONFIG
from backend.recommendation.contracts import RecommendationInputError


def profile(role="Platform Researcher", grade="Middle", requirements=None, critical=None):
    return {
        "role": role,
        "grade": grade,
        "required_skills": {"systems": 4, "writing": 2} if requirements is None else requirements,
        "critical_skills": ["systems"] if critical is None else critical,
    }


def employee(grade="Junior", goal=None, role="Platform Researcher"):
    return {
        "employee_id": "unseen-person-42",
        "role": role,
        "grade": grade,
        "career_goal": goal,
        "skills": {},
        "last_review_date": "2026-09-01",
    }


class ResolveTargetTests(unittest.TestCase):
    def setUp(self):
        self.profiles = [
            profile(role, grade)
            for role in ("Platform Researcher", "Service Designer")
            for grade in ("Junior", "Middle", "Senior", "Lead")
        ]

    def test_null_goal_uses_next_grade_in_current_role(self):
        result = resolve_target(employee(), self.profiles)
        self.assertEqual(result, {
            "status": "resolved",
            "target": {"role": "Platform Researcher", "grade": "Middle", "source": "next_grade"},
        })

    def test_explicit_transition_uses_destination_profile(self):
        person = employee("Middle", {"target_role": "Service Designer", "target_grade": "Middle"})
        self.assertEqual(resolve_target(person, self.profiles)["target"], {
            "role": "Service Designer", "grade": "Middle", "source": "career_goal",
        })

    def test_explicit_goal_precedes_terminal_grade_rule(self):
        person = employee("Lead", {"target_role": "Service Designer", "target_grade": "Senior"})
        self.assertEqual(resolve_target(person, self.profiles)["target"], {
            "role": "Service Designer", "grade": "Senior", "source": "career_goal",
        })

    def test_lead_without_goal_has_no_invented_next_grade(self):
        self.assertEqual(resolve_target(employee("Lead"), self.profiles), {
            "status": "no_next_grade", "target": None,
        })

    def test_explicit_real_profile_can_skip_grades(self):
        person = employee("Junior", {"target_role": "Platform Researcher", "target_grade": "Lead"})
        self.assertEqual(resolve_target(person, self.profiles)["target"]["grade"], "Lead")

    def test_current_grade_deficits_do_not_reject_or_downgrade_employee(self):
        person = employee("Senior")
        person["skills"] = {"systems": 0, "writing": 0}
        self.assertEqual(resolve_target(person, self.profiles)["target"]["grade"], "Lead")

    def test_catalog_order_does_not_change_target(self):
        person = employee("Middle", {"target_role": "Service Designer", "target_grade": "Senior"})
        self.assertEqual(
            resolve_target(person, self.profiles),
            resolve_target(person, list(reversed(self.profiles))),
        )

    def test_does_not_mutate_employee_or_profiles(self):
        person = employee()
        before = deepcopy((person, self.profiles))
        resolve_target(person, self.profiles)
        self.assertEqual((person, self.profiles), before)

    def test_unknown_target_and_unknown_current_profile_are_errors(self):
        cases = [
            employee("Junior", {"target_role": "Uncatalogued", "target_grade": "Middle"}),
            employee(role="Uncatalogued"),
            employee("Principal"),
        ]
        for person in cases:
            with self.subTest(person=person), self.assertRaises(RecommendationInputError) as raised:
                resolve_target(person, self.profiles)
            self.assertTrue(raised.exception.code)

    def test_missing_next_grade_profile_is_an_error(self):
        available = [p for p in self.profiles if p["grade"] != "Middle"]
        with self.assertRaises(RecommendationInputError):
            resolve_target(employee(), available)

    def test_duplicate_role_grade_keys_are_errors(self):
        with self.assertRaises(RecommendationInputError):
            resolve_target(employee(), self.profiles + [deepcopy(self.profiles[0])])

    def test_malformed_explicit_goals_do_not_fall_back_to_next_grade(self):
        for goal in ({}, [], "Senior", {"target_role": "Service Designer"},
                     {"target_role": "Service Designer", "target_grade": None}):
            with self.subTest(goal=goal), self.assertRaises(RecommendationInputError):
                resolve_target(employee(goal=goal), self.profiles)


class SkillGapTests(unittest.TestCase):
    def test_missing_skills_zero_and_only_positive_gaps_returned_in_priority_order(self):
        destination = profile(
            requirements={"a": 2, "b": 4, "c": 3, "d": 4, "e": 2},
            critical=["e", "c"],
        )
        actual = calculate_skill_gaps({"a": 5, "b": 1, "d": 1, "e": 1}, destination)
        self.assertEqual(actual, [
            {"skill_id": "c", "current": 0, "required": 3, "gap": 3, "critical": True},
            {"skill_id": "e", "current": 1, "required": 2, "gap": 1, "critical": True},
            {"skill_id": "b", "current": 1, "required": 4, "gap": 3, "critical": False},
            {"skill_id": "d", "current": 1, "required": 4, "gap": 3, "critical": False},
        ])

    def test_critical_set_comes_exactly_from_target_profile(self):
        prior = profile(grade="Middle", requirements={"coding": 3, "design": 2}, critical=["coding"])
        destination = profile(grade="Senior", requirements={"coding": 3, "design": 4}, critical=["design"])
        skills = {"coding": 1, "design": 1}
        self.assertTrue(calculate_skill_gaps(skills, prior)[0]["critical"])
        gaps = {gap["skill_id"]: gap for gap in calculate_skill_gaps(skills, destination)}
        self.assertFalse(gaps["coding"]["critical"])
        self.assertTrue(gaps["design"]["critical"])

    def test_extra_skills_and_zero_requirements_create_no_gaps(self):
        destination = profile(requirements={"systems": 0}, critical=[])
        self.assertEqual(calculate_skill_gaps({"unrelated": 5}, destination), [])

    def test_input_order_and_calling_both_calculations_do_not_mutate_inputs(self):
        skills = {"systems": 2, "writing": 1}
        destination = profile()
        before = deepcopy((skills, destination))
        gaps = calculate_skill_gaps(skills, destination)
        calculate_readiness(skills, destination)
        reversed_destination = deepcopy(destination)
        reversed_destination["required_skills"] = dict(reversed(list(destination["required_skills"].items())))
        self.assertEqual(calculate_skill_gaps(skills, reversed_destination), gaps)
        self.assertEqual((skills, destination), before)


class ReadinessTests(unittest.TestCase):
    def test_weighted_capped_coverage_has_hand_computed_result(self):
        result = calculate_readiness({"systems": 2, "writing": 5}, profile())
        # Critical systems contributes 2*2; writing is capped to its requirement 2.
        self.assertEqual(result["weighted_covered_levels"], 6)
        self.assertEqual(result["weighted_required_levels"], 10)
        self.assertAlmostEqual(result["current"], 0.6)
        self.assertEqual(result["critical_weight"], 2)
        self.assertEqual(result["status"], "available")
        self.assertIsNone(result["reason"])
        self.assertFalse(result["critical_requirements_met"])
        self.assertFalse(result["all_requirements_met"])
        self.assertEqual(result["remaining_critical_gaps"], [{
            "skill_id": "systems", "current": 2, "required": 4, "gap": 2, "critical": True,
        }])

    def test_critical_weight_is_configurable(self):
        config = replace(DEFAULT_CONFIG, readiness_critical_weight=3)
        result = calculate_readiness({"systems": 2, "writing": 2}, profile(), config=config)
        self.assertAlmostEqual(result["current"], 8 / 14)
        self.assertEqual(result["critical_weight"], 3)

    def test_missing_skills_start_at_zero_and_excess_cannot_compensate(self):
        result = calculate_readiness({"writing": 5, "unrelated": 5}, profile())
        self.assertAlmostEqual(result["current"], 0.2)
        self.assertFalse(result["critical_requirements_met"])

    def test_high_coverage_does_not_hide_missing_critical_requirement(self):
        requirements = {"critical": 5, **{"other_%s" % index: 5 for index in range(10)}}
        skills = dict(requirements, critical=4)
        result = calculate_readiness(skills, profile(requirements=requirements, critical=["critical"]))
        self.assertGreater(result["current"], 0.95)
        self.assertFalse(result["critical_requirements_met"])
        self.assertFalse(result["all_requirements_met"])

    def test_critical_satisfied_with_remaining_noncritical_gap(self):
        result = calculate_readiness({"systems": 4, "writing": 1}, profile())
        self.assertTrue(result["critical_requirements_met"])
        self.assertEqual(result["remaining_critical_gaps"], [])
        self.assertFalse(result["all_requirements_met"])
        self.assertAlmostEqual(result["current"], 0.9)

    def test_full_coverage_stops_at_one(self):
        result = calculate_readiness({"systems": 5, "writing": 5}, profile())
        self.assertEqual(result["current"], 1)
        self.assertTrue(result["critical_requirements_met"])
        self.assertTrue(result["all_requirements_met"])

    def test_no_critical_skills_and_no_positive_requirements(self):
        noncritical = calculate_readiness({"systems": 1}, profile(requirements={"systems": 2}, critical=[]))
        self.assertTrue(noncritical["critical_requirements_met"])
        for requirements in ({}, {"systems": 0}):
            with self.subTest(requirements=requirements):
                result = calculate_readiness({}, profile(requirements=requirements, critical=[]))
                self.assertEqual(result["status"], "unavailable")
                self.assertEqual(result["reason"], "no_positive_requirements")
                self.assertIsNone(result["current"])
                self.assertIsNone(result["critical_requirements_met"])
                self.assertIsNone(result["all_requirements_met"])
                self.assertEqual(result["remaining_critical_gaps"], [])

    def test_increasing_skills_never_reduces_coverage(self):
        destination = profile()
        for initial in range(5):
            with self.subTest(initial=initial):
                before = calculate_readiness({"systems": initial, "writing": 1}, destination)
                after = calculate_readiness({"systems": initial + 1, "writing": 1}, destination)
                self.assertGreaterEqual(after["current"], before["current"])
                self.assertLessEqual(after["current"], 1)


class CareerBoundaryValidationTests(unittest.TestCase):
    def test_invalid_levels_or_requirements_are_rejected(self):
        for calculate in (calculate_skill_gaps, calculate_readiness):
            for invalid in (-1, 6, True, 1.5, "2", None):
                with self.subTest(function=calculate.__name__, current=invalid):
                    with self.assertRaises(RecommendationInputError):
                        calculate({"systems": invalid}, profile())
                with self.subTest(function=calculate.__name__, required=invalid):
                    with self.assertRaises(RecommendationInputError):
                        calculate({}, profile(requirements={"systems": invalid}))

    def test_critical_skill_without_a_requirement_is_rejected(self):
        malformed = profile(requirements={"systems": 3}, critical=["missing"])
        for calculate in (calculate_skill_gaps, calculate_readiness):
            with self.subTest(function=calculate.__name__), self.assertRaises(RecommendationInputError):
                calculate({}, malformed)


if __name__ == "__main__":
    unittest.main()
