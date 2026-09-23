"""Event arithmetic and evidence for arbitrary, previously unseen skill IDs."""

from copy import deepcopy
from dataclasses import replace
import json
import unittest

from backend.recommendation.career import build_career_state
from backend.recommendation.config import DEFAULT_CONFIG
from backend.recommendation.contracts import RecommendationInputError
from backend.recommendation.simulation import simulate_event


def profile(requirements=None, critical=None):
    return {
        "role": "Research Engineer",
        "grade": "Middle",
        "required_skills": {"systems": 4, "writing": 2} if requirements is None else requirements,
        "critical_skills": ["systems"] if critical is None else critical,
    }


def development(skill_id, gain=1, max_level=5):
    return {"skill_id": skill_id, "gain": gain, "max_level": max_level}


def event(developments=None):
    return {
        "event_id": "unseen-event-2099",
        "format": "self_paced",
        "develops_skills": [development("systems")] if developments is None else developments,
    }


class SimulationTests(unittest.TestCase):
    def test_multiskill_event_has_hand_calculated_totals_readiness_and_closures(self):
        skills = {"systems": 2, "writing": 1, "unrelated": 2}
        destination = profile({"systems": 4, "writing": 2, "analysis": 3}, ["analysis", "systems"])
        activity = event([
            development("systems", 3),
            development("writing"),
            development("analysis", 2, 1),
            development("unrelated", 2, 4),
        ])
        result = simulate_event(skills, destination, activity)
        self.assertEqual(result["event_id"], "unseen-event-2099")
        self.assertEqual(result["target"], {"role": "Research Engineer", "grade": "Middle"})
        self.assertEqual(result["simulated_skills_after"], {
            "analysis": 1, "systems": 5, "unrelated": 4, "writing": 2,
        })
        self.assertEqual(
            [result[key] for key in ("total_gap_before", "total_gap_after", "total_gap_reduction")],
            [6, 2, 4],
        )
        self.assertEqual(
            [result[key] for key in ("critical_gap_before", "critical_gap_after", "critical_gap_reduction")],
            [5, 2, 3],
        )
        self.assertEqual(result["requirements_closed"], ["systems", "writing"])
        self.assertEqual(result["critical_requirements_closed"], ["systems"])
        self.assertAlmostEqual(result["readiness_before"], 5 / 16)
        self.assertAlmostEqual(result["readiness_after"], 12 / 16)
        self.assertAlmostEqual(result["readiness_delta"], 7 / 16)
        self.assertEqual(result["skill_gaps_after"], [{
            "skill_id": "analysis", "current": 1, "required": 3, "gap": 2, "critical": True,
        }])
        self.assertEqual(result["critical_gaps_after"], result["skill_gaps_after"])
        self.assertFalse(result["readiness_after_details"]["critical_requirements_met"])

    def test_raw_gains_and_useful_gains_are_distinct_evidence(self):
        result = simulate_event(
            {"systems": 2}, profile(), event([development("systems", 3), development("unrelated", 2)]),
        )
        self.assertEqual(result["skill_impact"], [
            {"skill_id": "systems", "before": 2, "advertised_gain": 3,
             "max_level": 5, "after": 5, "actual_gain": 3},
            {"skill_id": "unrelated", "before": 0, "advertised_gain": 2,
             "max_level": 5, "after": 2, "actual_gain": 2},
        ])
        self.assertEqual(result["target_skill_impact"], [{
            "skill_id": "systems", "current": 2, "required": 4, "gap_before": 2,
            "after": 5, "gap_after": 0, "useful_gain": 2, "critical": True,
        }])
        self.assertEqual(result["total_gap_reduction"], 2)
        # Writing was untouched, but still belongs to the total target gap.
        self.assertEqual(result["total_gap_after"], 2)

    def test_gain_limited_by_cap_without_closing_requirement(self):
        result = simulate_event({"systems": 2}, profile(), event([development("systems", 4, 3)]))
        self.assertEqual(result["skill_impact"][0]["actual_gain"], 1)
        self.assertEqual(result["simulated_skills_after"]["systems"], 3)
        self.assertEqual(result["target_skill_impact"][0]["gap_after"], 1)
        self.assertEqual(result["requirements_closed"], [])
        self.assertEqual(result["critical_requirements_closed"], [])

    def test_level_above_cap_never_decreases_even_when_gap_remains(self):
        result = simulate_event({"systems": 4}, profile({"systems": 5}), event([development("systems", 2, 3)]))
        self.assertEqual(result["skill_impact"][0]["actual_gain"], 0)
        self.assertEqual(result["simulated_skills_after"]["systems"], 4)
        self.assertEqual(result["total_gap_before"], 1)
        self.assertEqual(result["total_gap_after"], 1)
        self.assertEqual(result["readiness_delta"], 0)
        self.assertEqual(result["target_skill_impact"][0]["useful_gain"], 0)

    def test_level_at_cap_retains_zero_gain_evidence(self):
        result = simulate_event({"systems": 3}, profile(), event([development("systems", 1, 3)]))
        self.assertEqual(len(result["skill_impact"]), 1)
        self.assertEqual(len(result["target_skill_impact"]), 1)
        self.assertEqual(result["skill_impact"][0]["actual_gain"], 0)
        self.assertEqual(result["total_gap_reduction"], 0)

    def test_missing_skill_is_zero_with_arbitrary_skill_ids(self):
        result = simulate_event({}, profile({"jury::skill-42": 3}, ["jury::skill-42"]),
                                event([development("jury::skill-42", 2)]))
        self.assertEqual(result["skill_impact"][0]["before"], 0)
        self.assertEqual(result["simulated_skills_after"], {"jury::skill-42": 2})
        self.assertEqual(result["critical_gap_reduction"], 2)
        self.assertAlmostEqual(result["readiness_after"], 2 / 3)

    def test_improving_irrelevant_skill_leaves_readiness_unchanged(self):
        result = simulate_event({"systems": 2}, profile(), event([development("unrelated", 2)]))
        self.assertEqual(result["skill_impact"][0]["actual_gain"], 2)
        self.assertEqual(result["target_skill_impact"], [])
        self.assertEqual(result["total_gap_reduction"], 0)
        self.assertEqual(result["critical_gap_reduction"], 0)
        self.assertEqual(result["readiness_before"], result["readiness_after"])
        self.assertEqual(result["readiness_delta"], 0)

    def test_gain_above_satisfied_requirement_is_not_useful_or_new_closure(self):
        result = simulate_event({"systems": 4}, profile(), event())
        self.assertEqual(result["skill_impact"][0]["actual_gain"], 1)
        self.assertEqual(result["target_skill_impact"][0]["gap_before"], 0)
        self.assertEqual(result["target_skill_impact"][0]["useful_gain"], 0)
        self.assertEqual(result["requirements_closed"], [])
        self.assertEqual(result["critical_requirements_closed"], [])
        self.assertEqual(result["readiness_delta"], 0)

    def test_closing_final_requirement_reaches_one_with_critical_indicator(self):
        result = simulate_event({"systems": 3, "writing": 2}, profile(), event())
        self.assertEqual(result["readiness_before"], 0.8)
        self.assertEqual(result["readiness_after"], 1)
        self.assertEqual(result["total_gap_after"], 0)
        self.assertEqual(result["critical_gap_after"], 0)
        self.assertEqual(result["requirements_closed"], ["systems"])
        self.assertTrue(result["readiness_after_details"]["critical_requirements_met"])
        self.assertTrue(result["readiness_after_details"]["all_requirements_met"])

    def test_noncritical_closure_does_not_enter_critical_closures(self):
        result = simulate_event({"systems": 1, "writing": 1}, profile(), event([development("writing")]))
        self.assertEqual(result["requirements_closed"], ["writing"])
        self.assertEqual(result["critical_requirements_closed"], [])
        self.assertEqual(result["critical_gap_reduction"], 0)
        self.assertAlmostEqual(result["readiness_delta"], 0.1)

    def test_critical_impact_uses_only_exact_destination_critical_set(self):
        result = simulate_event(
            {"systems": 2, "writing": 1}, profile(critical=["writing"]),
            event([development("systems", 2), development("writing")]),
        )
        impacts = {item["skill_id"]: item for item in result["target_skill_impact"]}
        self.assertFalse(impacts["systems"]["critical"])
        self.assertTrue(impacts["writing"]["critical"])
        self.assertEqual(result["critical_requirements_closed"], ["writing"])
        self.assertEqual(result["critical_gap_reduction"], 1)
        self.assertEqual(result["total_gap_reduction"], 3)

    def test_empty_and_zero_requirements_keep_readiness_unavailable(self):
        for requirements in ({}, {"systems": 0}):
            with self.subTest(requirements=requirements):
                result = simulate_event({}, profile(requirements, []), event())
                self.assertIsNone(result["readiness_before"])
                self.assertIsNone(result["readiness_after"])
                self.assertIsNone(result["readiness_delta"])
                self.assertEqual(result["readiness_after_details"]["reason"], "no_positive_requirements")
                self.assertEqual(result["total_gap_before"], 0)
                self.assertEqual(result["total_gap_after"], 0)
                self.assertEqual(result["requirements_closed"], [])

    def test_empty_developments_and_zero_gain_are_valid_hypothetical_noops(self):
        for activity in (event([]), event([development("systems", 0)])):
            with self.subTest(event=activity):
                result = simulate_event({"systems": 2}, profile(), activity)
                self.assertEqual(result["simulated_skills_after"], {"systems": 2})
                self.assertEqual(result["readiness_delta"], 0)
                self.assertEqual(result["total_gap_reduction"], 0)

    def test_admission_fields_do_not_gate_hypothetical_simulation(self):
        activity = event()
        activity.update({
            "mandatory": True, "target_roles": [], "target_grades": [],
            "prerequisites": {"systems": 5}, "upcoming_sessions": [],
        })
        result = simulate_event({"systems": 2}, profile(), activity)
        self.assertEqual(result["total_gap_reduction"], 1)
        self.assertGreater(result["readiness_delta"], 0)

    def test_configured_critical_weight_flows_through_existing_readiness(self):
        result = simulate_event(
            {"systems": 2, "writing": 2}, profile(), event(),
            config=replace(DEFAULT_CONFIG, readiness_critical_weight=3),
        )
        self.assertAlmostEqual(result["readiness_before"], 8 / 14)
        self.assertAlmostEqual(result["readiness_after"], 11 / 14)
        self.assertAlmostEqual(result["readiness_delta"], 3 / 14)
        self.assertEqual(result["readiness_after_details"]["critical_weight"], 3)

    def test_all_collections_are_deterministic_across_input_order(self):
        skills = {"writing": 1, "systems": 2, "extra": 0}
        destination = profile({"writing": 2, "systems": 4}, ["systems", "writing"])
        activity = event([development("writing"), development("systems", 2), development("extra")])
        reordered_profile = deepcopy(destination)
        reordered_profile["required_skills"] = dict(reversed(list(destination["required_skills"].items())))
        reordered_profile["critical_skills"].reverse()
        reordered_event = deepcopy(activity)
        reordered_event["develops_skills"].reverse()
        first = simulate_event(skills, destination, activity)
        second = simulate_event(dict(reversed(list(skills.items()))), reordered_profile, reordered_event)
        self.assertEqual(json.dumps(first), json.dumps(second))
        self.assertEqual(first["requirements_closed"], ["systems", "writing"])

    def test_simulation_and_returned_evidence_do_not_mutate_career_state(self):
        person = {
            "employee_id": "unseen-person", "role": "Research Engineer", "grade": "Junior",
            "career_goal": None, "skills": {"systems": 1, "writing": 1},
            "last_review_date": "2026-01-01",
        }
        destination = profile()
        current_profile = dict(destination, grade="Junior")
        activity = event()
        history = [{
            "record_id": "unseen-record", "employee_id": "unseen-person",
            "event_id": activity["event_id"], "status": "completed", "date": "2026-09-01",
        }]
        state = build_career_state(person, [current_profile, destination], [activity], history, as_of="2026-10-01")
        inputs_before = deepcopy((person, destination, activity, state))
        result = simulate_event(state["skills_reconstruction"]["effective_skills"], destination, activity)
        self.assertEqual(result["skill_impact"][0]["before"], 2)
        self.assertEqual((person, destination, activity, state), inputs_before)
        # A caller may annotate/mutate the response; no nested object aliases an input.
        result["simulated_skills_after"]["systems"] = 0
        result["target"]["role"] = "Changed"
        result["skill_impact"][0]["after"] = 0
        result["target_skill_impact"][0]["required"] = 0
        result["skill_gaps_before"][0]["required"] = 0
        result["readiness_before_details"]["remaining_critical_gaps"][0]["gap"] = 0
        self.assertEqual((person, destination, activity, state), inputs_before)

    def test_alternatives_start_from_same_baseline_instead_of_accumulating(self):
        skills = {"systems": 1}
        activity = event()
        first = simulate_event(skills, profile(), activity)
        second = simulate_event(skills, profile(), activity)
        self.assertEqual(first, second)
        self.assertEqual(second["simulated_skills_after"]["systems"], 2)
        self.assertEqual(skills["systems"], 1)


class SimulationBoundaryTests(unittest.TestCase):
    def test_duplicate_developed_skill_is_not_silently_counted_twice(self):
        with self.assertRaises(RecommendationInputError) as raised:
            simulate_event({}, profile(), event([development("systems"), development("systems")]))
        self.assertEqual(raised.exception.code, "duplicate_developed_skill")

    def test_invalid_gain_and_cap_values_fail_safely(self):
        for value in (-1, True, 1.5, "2", None):
            with self.subTest(gain=value), self.assertRaises(RecommendationInputError) as raised:
                simulate_event({}, profile(), event([development("systems", value)]))
            self.assertEqual(raised.exception.code, "invalid_gain")
        for value in (-1, 6, True, 1.5, "2", None):
            with self.subTest(cap=value), self.assertRaises(RecommendationInputError) as raised:
                simulate_event({}, profile(), event([development("systems", 1, value)]))
            self.assertEqual(raised.exception.code, "invalid_skill_level")

    def test_invalid_current_required_and_critical_levels_fail_safely(self):
        for value in (-1, 6, True, 1.5, "2", None):
            with self.subTest(current=value), self.assertRaises(RecommendationInputError):
                simulate_event({"systems": value}, profile(), event())
            with self.subTest(required=value), self.assertRaises(RecommendationInputError):
                simulate_event({}, profile({"systems": value}), event())
        for critical in (["unknown"], ["systems", "systems"], "systems", None):
            with self.subTest(critical=critical), self.assertRaises(RecommendationInputError):
                destination = profile()
                destination["critical_skills"] = critical
                simulate_event({}, destination, event())

    def test_malformed_minimal_boundary_records_raise_domain_errors(self):
        for invalid_event in (None, [], {}, {"event_id": "x", "format": "self_paced"},
                              event([{}]), event([development("")])):
            with self.subTest(event=invalid_event), self.assertRaises(RecommendationInputError):
                simulate_event({}, profile(), invalid_event)
        for invalid_profile in (None, {}, dict(profile(), role=""), dict(profile(), grade=None)):
            with self.subTest(profile=invalid_profile), self.assertRaises(RecommendationInputError):
                simulate_event({}, invalid_profile, event())
        with self.assertRaises(RecommendationInputError):
            simulate_event([], profile(), event())


if __name__ == "__main__":
    unittest.main()
