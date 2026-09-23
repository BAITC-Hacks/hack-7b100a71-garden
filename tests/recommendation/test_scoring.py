"""Hand-calculated scoring, normalization and boundary behavior without ranking."""

from copy import deepcopy
from dataclasses import replace
import json
from math import fsum, isfinite
import unittest

from backend.recommendation.config import DEFAULT_CONFIG, ScoringWeights
from backend.recommendation.contracts import RecommendationInputError
from backend.recommendation.scoring import score_candidates
from backend.recommendation.simulation import simulate_event


def event(event_id="jury-candidate", develops=None, duration=2, scheduled=False):
    return {
        "event_id": event_id,
        "format": "online" if scheduled else "self_paced",
        "duration_hours": duration,
        "develops_skills": [
            {"skill_id": skill, "gain": gain, "max_level": cap}
            for skill, gain, cap in ([("critical", 1, 5)] if develops is None else develops)
        ],
    }


def candidate(activity, skills=None, requirements=None, critical=None, wait=30):
    profile = {
        "role": "Unseen Research Role", "grade": "Senior",
        "required_skills": {"critical": 4, "gap": 4} if requirements is None else requirements,
        "critical_skills": ["critical"] if critical is None else critical,
    }
    self_paced = activity["format"] == "self_paced"
    return {
        "event_id": activity["event_id"], "title": "Unseen activity",
        "eligible": True, "rejection_reasons": [],
        "simulation": simulate_event(
            {"critical": 1, "gap": 1} if skills is None else skills, profile, activity,
        ),
        "evidence": {"availability": {
            "format": activity["format"], "available": True, "self_paced": self_paced,
            "next_session_date": None if self_paced else "2026-10-31",
            "days_until_next_session": 0 if self_paced else wait,
        }},
    }


def signals(*activities, compatibility=0.5, feedback=0.5):
    return {activity["event_id"]: {
        "compatibility": compatibility, "feedback_signal": feedback,
        "evidence": {"matched_history_count": 0},
    } for activity in activities}


class ScoringTests(unittest.TestCase):
    def test_all_seven_factors_have_hand_computed_values_and_contributions(self):
        first = event("a", [("critical", 2, 5), ("gap", 1, 5)], duration=3)
        second = event("b", [("critical", 1, 5), ("gap", 3, 5), ("unrelated", 2, 5)], duration=2, scheduled=True)
        history = signals(first, second)
        history["a"].update(compatibility=0.4, feedback_signal=0.75)
        history["b"].update(compatibility=0.9, feedback_signal=0.2)
        scored = score_candidates([candidate(first), candidate(second)], [first, second], history)
        self.assertEqual([item["event_id"] for item in scored], ["a", "b"])
        factors_a = {
            "critical_skill_impact": (2, 1, 0.35),
            "gap_reduction": (3, 0.75, 0.25),
            "career_relevance": (1, 1, 0.15),
            "historical_compatibility": (0.4, 0.4, 0.1),
            "history_feedback_signal": (0.75, 0.75, 0.05),
            "effort_efficiency": (1, 0.5, 0.05),
            "availability": (1, 1, 0.05),
        }
        for name, (raw, normalized, weight) in factors_a.items():
            with self.subTest(factor=name):
                factor = scored[0]["factors"][name]
                self.assertEqual(factor["raw"], raw)
                self.assertEqual(factor["normalized"], normalized)
                self.assertEqual(factor["weight"], weight)
                self.assertEqual(factor["contribution"], normalized * weight)
        self.assertAlmostEqual(scored[0]["score"], 0.84)
        self.assertAlmostEqual(scored[1]["score"], 0.70)
        self.assertEqual(scored[1]["factors"]["career_relevance"]["normalized"], 2 / 3)
        self.assertEqual(scored[1]["factors"]["availability"]["normalized"], 0.5)
        self.assertEqual(scored[0]["scoring_evidence"], {
            "useful_destination_gain": 3, "advertised_positive_gain": 3,
            "duration_hours": 3.0, "duration_valid": True, "raw_efficiency": 1.0,
            "availability_wait_days": 0, "normalization_candidate_count": 2,
            "normalization_maxima": {
                "critical_skill_impact": 2, "gap_reduction": 4, "effort_efficiency": 2,
            },
        })

    def test_relevance_denominator_is_actual_capped_gain_not_nominal_gain(self):
        activity = event(develops=[("critical", 3, 3), ("unrelated", 5, 1)])
        result = score_candidates(
            [candidate(activity, skills={"critical": 2}, requirements={"critical": 3})],
            [activity], signals(activity),
        )[0]
        # The nominal sum is 8; caps produce one useful and one unrelated gain.
        self.assertEqual(result["scoring_evidence"]["advertised_positive_gain"], 2)
        self.assertEqual(result["scoring_evidence"]["useful_destination_gain"], 1)
        self.assertEqual(result["factors"]["career_relevance"]["normalized"], 0.5)

    def test_relevance_excludes_gain_beyond_target_and_includes_unrelated_gain_in_denominator(self):
        activity = event(develops=[("critical", 4, 5), ("unrelated", 1, 5)])
        result = score_candidates(
            [candidate(activity, skills={"critical": 1}, requirements={"critical": 3})],
            [activity], signals(activity),
        )[0]
        self.assertEqual(result["scoring_evidence"]["advertised_positive_gain"], 5)
        self.assertEqual(result["scoring_evidence"]["useful_destination_gain"], 2)
        self.assertEqual(result["factors"]["career_relevance"]["normalized"], 0.4)

    def test_irrelevant_extra_gains_reduce_relevance_against_useful_only_event(self):
        distracted = event("distracted", [("critical", 1, 5), ("extra", 3, 5)])
        focused = event("focused")
        result = score_candidates(
            [candidate(distracted), candidate(focused)], [distracted, focused], signals(distracted, focused),
        )
        self.assertEqual(result[0]["factors"]["career_relevance"]["normalized"], 0.25)
        self.assertEqual(result[1]["factors"]["career_relevance"]["normalized"], 1)
        self.assertGreater(result[1]["score"], result[0]["score"])

    def test_multigap_event_receives_larger_gap_and_relevance_factors(self):
        multiple = event("multiple", [("critical", 1, 5), ("gap", 1, 5)])
        single = event("single", [("gap", 1, 5), ("unrelated", 1, 5)])
        results = score_candidates([candidate(multiple), candidate(single)], [multiple, single], signals(multiple, single))
        self.assertEqual(results[0]["factors"]["gap_reduction"]["normalized"], 1)
        self.assertEqual(results[1]["factors"]["gap_reduction"]["normalized"], 0.5)
        self.assertEqual(results[0]["factors"]["career_relevance"]["normalized"], 1)
        self.assertEqual(results[1]["factors"]["career_relevance"]["normalized"], 0.5)

    def test_critical_career_value_can_outweigh_excellent_noncritical_history(self):
        critical = event("z-critical")
        noncritical = event("a-noncritical", [("gap", 1, 5)])
        history = signals(critical, noncritical)
        history[critical["event_id"]].update(compatibility=0.2, feedback_signal=0.3)
        history[noncritical["event_id"]].update(compatibility=0.95, feedback_signal=0.95)
        result = score_candidates([candidate(critical), candidate(noncritical)], [critical, noncritical], history)
        # Scoring returns ID order, deliberately without ranking the winner first.
        self.assertEqual(result[0]["event_id"], "a-noncritical")
        self.assertGreater(result[1]["score"], result[0]["score"])

    def test_normalization_uses_complete_pool_before_any_selection(self):
        first = event("a", [("critical", 2, 5), ("gap", 1, 5)], duration=3)
        stronger = event("z", [("critical", 3, 5), ("gap", 3, 5)], duration=1)
        result = score_candidates([candidate(first), candidate(stronger)], [first, stronger], signals(first, stronger))
        self.assertEqual(len(result), 2)
        first_score = result[0]
        self.assertEqual(first_score["factors"]["critical_skill_impact"]["normalized"], 2 / 3)
        self.assertEqual(first_score["factors"]["gap_reduction"]["normalized"], 0.5)
        self.assertEqual(first_score["factors"]["effort_efficiency"]["normalized"], 1 / 6)
        self.assertEqual(first_score["scoring_evidence"]["normalization_candidate_count"], 2)

    def test_no_critical_gains_does_not_redistribute_critical_weight(self):
        activity = event(develops=[("gap", 1, 5)])
        result = score_candidates([candidate(activity)], [activity], signals(activity))[0]
        critical = result["factors"]["critical_skill_impact"]
        self.assertEqual(critical, {"raw": 0, "normalized": 0, "weight": 0.35, "contribution": 0})
        self.assertAlmostEqual(result["score"], 0.575)
        self.assertEqual(result["scoring_evidence"]["normalization_maxima"]["critical_skill_impact"], 0)

    def test_zero_gain_numeric_conventions_never_divide_by_zero(self):
        activity = event(develops=[("critical", 0, 5)])
        # Step 2 normally filters this out; scoring arithmetic still has a defined zero convention.
        result = score_candidates([candidate(activity)], [activity], signals(activity))[0]
        for factor in ("critical_skill_impact", "gap_reduction", "career_relevance", "effort_efficiency"):
            self.assertEqual(result["factors"][factor]["normalized"], 0)
        self.assertAlmostEqual(result["score"], 0.125)

    def test_numeric_duration_strings_and_numbers_are_accepted(self):
        for duration in (2, 2.0, "2", " 2.0 "):
            with self.subTest(duration=duration):
                activity = event(duration=duration)
                result = score_candidates([candidate(activity)], [activity], signals(activity))[0]
                self.assertEqual(result["scoring_evidence"]["duration_hours"], 2.0)
                self.assertTrue(result["scoring_evidence"]["duration_valid"])
                self.assertEqual(result["factors"]["effort_efficiency"]["raw"], 0.5)

    def test_invalid_durations_and_unrepresentable_efficiency_receive_zero_effort_credit(self):
        invalid = [None, 0, -2, True, "", "bad", "NaN", "Infinity", float("nan"), float("inf"), {}, [], 5e-324]
        for duration in invalid:
            with self.subTest(duration=duration):
                activity = event(duration=duration)
                result = score_candidates([candidate(activity)], [activity], signals(activity))[0]
                self.assertIsNone(result["scoring_evidence"]["duration_hours"])
                self.assertFalse(result["scoring_evidence"]["duration_valid"])
                self.assertEqual(result["factors"]["effort_efficiency"]["raw"], 0)
                self.assertEqual(result["factors"]["effort_efficiency"]["normalized"], 0)
                self.assertTrue(isfinite(result["score"]))
        activity = event()
        del activity["duration_hours"]
        result = score_candidates([candidate(activity)], [activity], signals(activity))[0]
        self.assertIsNone(result["scoring_evidence"]["duration_hours"])

    def test_bad_duration_does_not_prevent_valid_candidate_efficiency_normalization(self):
        missing = event("missing", duration=None)
        valid = event("valid", duration=4)
        result = score_candidates([candidate(missing), candidate(valid)], [missing, valid], signals(missing, valid))
        self.assertEqual(result[0]["factors"]["effort_efficiency"]["normalized"], 0)
        self.assertEqual(result[1]["factors"]["effort_efficiency"]["normalized"], 1)
        self.assertEqual(result[1]["scoring_evidence"]["normalization_maxima"]["effort_efficiency"], 0.25)

    def test_custom_weights_and_availability_scale_are_used_without_rounding(self):
        activity = event(scheduled=True)
        weights = ScoringWeights(
            critical_skill_impact=0.10, gap_reduction=0.20, career_relevance=0.30,
            historical_compatibility=0.15, history_feedback_signal=0.10,
            effort_efficiency=0.05, availability=0.10,
        )
        config = replace(DEFAULT_CONFIG, scoring_weights=weights, availability_wait_scale_days=60)
        result = score_candidates([candidate(activity)], [activity], signals(activity), config=config)[0]
        self.assertEqual(result["factors"]["availability"]["normalized"], 2 / 3)
        self.assertEqual(result["factors"]["availability"]["contribution"], 0.1 * (2 / 3))
        self.assertEqual(result["score"], fsum(f["contribution"] for f in result["factors"].values()))
        for name, value in vars(weights).items():
            self.assertEqual(result["factors"][name]["weight"], value)

    def test_input_order_idempotence_and_response_mutation_do_not_affect_inputs(self):
        activities = [event("z"), event("a", [("gap", 1, 5)], scheduled=True)]
        candidates = [candidate(activity) for activity in activities]
        history = signals(*activities)
        before = deepcopy((candidates, activities, history))
        first = score_candidates(candidates, activities, history)
        second = score_candidates(list(reversed(candidates)), list(reversed(activities)), dict(reversed(list(history.items()))))
        self.assertEqual(json.dumps(first), json.dumps(second))
        self.assertEqual((candidates, activities, history), before)
        first[0]["factors"]["gap_reduction"]["raw"] = 999
        first[0]["scoring_evidence"]["normalization_maxima"]["gap_reduction"] = 999
        self.assertEqual((candidates, activities, history), before)
        self.assertEqual(score_candidates(candidates, activities, history), second)
        self.assertEqual(first[1]["scoring_evidence"]["normalization_maxima"]["gap_reduction"], 1)

    def test_empty_eligible_pool_returns_empty_without_fake_candidates(self):
        self.assertEqual(score_candidates([], [], {}), [])


class ScoringBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.activity = event()
        self.candidate = candidate(self.activity)
        self.history = signals(self.activity)

    def score(self, **changes):
        values = {"candidates": [self.candidate], "events": [self.activity], "history_signals": self.history}
        values.update(changes)
        return score_candidates(**values)

    def test_ineligible_duplicate_unknown_and_mismatched_candidates_raise_domain_errors(self):
        invalids = [dict(self.candidate, eligible=False), dict(self.candidate, rejection_reasons=[{"code": "MANDATORY"}]),
                    dict(self.candidate, event_id="not-in-catalog"), dict(self.candidate, simulation=None)]
        for invalid in invalids:
            with self.subTest(candidate=invalid), self.assertRaises(RecommendationInputError):
                self.score(candidates=[invalid])
        with self.assertRaises(RecommendationInputError) as raised:
            self.score(candidates=[self.candidate, deepcopy(self.candidate)])
        self.assertEqual(raised.exception.code, "duplicate_candidate")
        with self.assertRaises(RecommendationInputError):
            self.score(events=[self.activity, deepcopy(self.activity)])

    def test_missing_and_out_of_range_history_signals_raise_domain_errors(self):
        for signal in ({}, None):
            with self.subTest(signal=signal), self.assertRaises(RecommendationInputError):
                self.score(history_signals=signal)
        for key in ("compatibility", "feedback_signal"):
            for value in (-0.1, 1.1, True, None, "0.5", float("nan"), float("inf"), 10 ** 500):
                with self.subTest(key=key, value=value), self.assertRaises(RecommendationInputError):
                    modified = deepcopy(self.history)
                    modified[self.activity["event_id"]][key] = value
                    self.score(history_signals=modified)

    def test_inconsistent_or_invalid_simulation_is_not_scored(self):
        for key, value in (("total_gap_reduction", -1), ("critical_gap_reduction", True),
                           ("total_gap_before", 99), ("skill_impact", None), ("target_skill_impact", None)):
            with self.subTest(key=key), self.assertRaises(RecommendationInputError):
                modified = deepcopy(self.candidate)
                modified["simulation"][key] = value
                self.score(candidates=[modified])
        for field, value in (("useful_gain", 2), ("critical", "yes")):
            with self.subTest(field=field), self.assertRaises(RecommendationInputError):
                modified = deepcopy(self.candidate)
                modified["simulation"]["target_skill_impact"][0][field] = value
                self.score(candidates=[modified])
        for list_name in ("skill_impact", "target_skill_impact"):
            with self.subTest(list_name=list_name), self.assertRaises(RecommendationInputError):
                modified = deepcopy(self.candidate)
                modified["simulation"][list_name].append(deepcopy(modified["simulation"][list_name][0]))
                self.score(candidates=[modified])

    def test_malformed_availability_is_not_silently_repaired(self):
        changes = [("available", False), ("self_paced", False), ("self_paced", 1),
                   ("format", "online"), ("days_until_next_session", -1),
                   ("days_until_next_session", 1), ("next_session_date", "2026-10-31")]
        for key, value in changes:
            with self.subTest(key=key, value=value), self.assertRaises(RecommendationInputError):
                modified = deepcopy(self.candidate)
                modified["evidence"]["availability"][key] = value
                self.score(candidates=[modified])
        scheduled = event(scheduled=True)
        invalid = candidate(scheduled)
        invalid["evidence"]["availability"]["next_session_date"] = "not-a-date"
        with self.assertRaises(RecommendationInputError):
            self.score(candidates=[invalid], events=[scheduled])

    def test_nonsequence_wrappers_and_nonmapping_candidate_raise_domain_errors(self):
        for changes in ({"candidates": {}}, {"events": {}}, {"candidates": [None]}, {"history_signals": []}):
            with self.subTest(changes=changes), self.assertRaises(RecommendationInputError):
                self.score(**changes)


if __name__ == "__main__":
    unittest.main()
