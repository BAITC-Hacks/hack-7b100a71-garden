"""Unseen-profile ranking, jury traps and stable recommendation orchestration."""

from copy import deepcopy
from dataclasses import replace
from math import fsum, isfinite
import json
import unittest

from backend.recommendation.career import build_career_state
from backend.recommendation.config import DEFAULT_CONFIG, ScoringWeights
from backend.recommendation.contracts import RecommendationInputError
from backend.recommendation.engine import recommend


AS_OF = "2026-10-01"
ROLE = "Unseen Platform Engineer"
DESTINATION = "Unseen Product Architect"
PERSON_ID = "jury-person-813"


def employee(**changes):
    result = {
        "employee_id": PERSON_ID,
        "role": ROLE,
        "grade": "Middle",
        "career_goal": None,
        "skills": {"system-design": 2, "public-speaking": 0},
        "last_review_date": "2026-08-01",
    }
    result.update(changes)
    return result


def profiles(required=None, critical=None):
    required = {"system-design": 4, "public-speaking": 2} if required is None else required
    critical = ["system-design"] if critical is None else critical
    return [{
        "role": role,
        "grade": grade,
        "required_skills": dict(required),
        "critical_skills": list(critical),
    } for role in (ROLE, DESTINATION) for grade in DEFAULT_CONFIG.grades]


def event(event_id, gains=None, **changes):
    gains = {"system-design": 1} if gains is None else gains
    result = {
        "event_id": event_id,
        "title": "Unseen event " + event_id,
        "type": "workshop",
        "format": "self_paced",
        "mandatory": False,
        "target_roles": [ROLE],
        "target_grades": ["Middle"],
        "prerequisites": {},
        "upcoming_sessions": [],
        "duration_hours": 4,
        "develops_skills": [
            {"skill_id": skill_id, "gain": gain, "max_level": 5}
            for skill_id, gain in gains.items()
        ],
    }
    result.update(changes)
    return result


def participation(record_id, event_id, status="no_show", **changes):
    result = {
        "record_id": record_id,
        "employee_id": PERSON_ID,
        "event_id": event_id,
        "date": "2026-07-01",
        "status": status,
        "assigned_by": "self",
        "completion_pct": 100 if status == "completed" else 0,
        "feedback_rating": None,
        "score": None,
    }
    result.update(changes)
    return result


def ids(result):
    return [item["event_id"] for item in result["recommendations"]]


def by_id(result):
    return {item["event_id"]: item for item in result["recommendations"]}


def normalized(item, factor):
    return item["factors"][factor]["normalized"]


# Cold-start H is exactly the same for every candidate; all subsequent ordering
# must therefore come from the documented tie-break rules, not a score proxy.
TIE_CONFIG = replace(DEFAULT_CONFIG, scoring_weights=ScoringWeights(
    critical_skill_impact=0, gap_reduction=0, career_relevance=0,
    historical_compatibility=1, history_feedback_signal=0,
    effort_efficiency=0, availability=0,
))


class RecommendationEngineTests(unittest.TestCase):
    def run_engine(self, catalog=None, history=None, person=None, role_profiles=None, **kwargs):
        return recommend(
            employee() if person is None else person,
            profiles() if role_profiles is None else role_profiles,
            [event("single-unseen-event")] if catalog is None else catalog,
            [] if history is None else history,
            as_of=AS_OF, **kwargs,
        )

    def test_jury_a_lowest_skill_is_not_the_best_recommendation(self):
        catalog = [
            event("speech-session", {"public-speaking": 1}, type="meetup",
                  format="offline", upcoming_sessions=[AS_OF]),
            event("systems-session", {"system-design": 1}, type="course"),
        ]
        history = [participation("miss-{}".format(index), "speech-session") for index in range(6)]
        result = self.run_engine(catalog, history)
        ranked = by_id(result)
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(ids(result), ["systems-session", "speech-session"])
        self.assertEqual(ranked["systems-session"]["simulation"]["critical_gap_reduction"], 1)
        self.assertEqual(ranked["speech-session"]["simulation"]["critical_gap_reduction"], 0)
        self.assertLess(normalized(ranked["speech-session"], "historical_compatibility"), 0.5)
        self.assertLess(normalized(ranked["speech-session"], "historical_compatibility"),
                        normalized(ranked["systems-session"], "historical_compatibility"))

    def test_jury_b_negative_history_does_not_veto_critical_career_value(self):
        critical = event("critical-future", format="online", type="course", upcoming_sessions=[AS_OF])
        noncritical = event("noncritical-future", {"public-speaking": 1},
                            format="offline", type="meetup", upcoming_sessions=[AS_OF])
        old_positive = [event("historical-speech-{}".format(i), {"public-speaking": 1},
                              format="offline", type="meetup", upcoming_sessions=[AS_OF])
                        for i in range(8)]
        history = [participation("critical-miss-{}".format(i), "critical-future") for i in range(2)]
        history += [participation("speech-completion-{}".format(i), old_event["event_id"], "completed",
                                  feedback_rating=5) for i, old_event in enumerate(old_positive)]
        result = self.run_engine([critical, noncritical] + old_positive, history)
        ranked = by_id(result)
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(ids(result)[0], "critical-future")
        self.assertLess(normalized(ranked["critical-future"], "historical_compatibility"), 0.5)
        self.assertGreater(normalized(ranked["noncritical-future"], "historical_compatibility"), 0.5)
        self.assertGreater(ranked["critical-future"]["score"], ranked["noncritical-future"]["score"])

    def test_jury_c_multiple_destination_gaps_gain_gap_and_relevance_advantage(self):
        catalog = [
            event("multi-gap", {"public-speaking": 1, "writing": 1}),
            event("one-gap", {"public-speaking": 1, "unrelated-skill": 1}),
        ]
        result = self.run_engine(catalog, role_profiles=profiles(
            {"public-speaking": 2, "writing": 2}, critical=[],
        ))
        ranked = by_id(result)
        self.assertEqual(ids(result), ["multi-gap", "one-gap"])
        self.assertEqual(normalized(ranked["multi-gap"], "gap_reduction"), 1)
        self.assertEqual(normalized(ranked["one-gap"], "gap_reduction"), 0.5)
        self.assertEqual(normalized(ranked["multi-gap"], "career_relevance"), 1)
        self.assertEqual(normalized(ranked["one-gap"], "career_relevance"), 0.5)
        # No critical requirement means no redistribution of the unused C weight.
        self.assertEqual(normalized(ranked["multi-gap"], "critical_skill_impact"), 0)
        self.assertLessEqual(ranked["multi-gap"]["score"], 0.65)

    def test_jury_d_irrelevant_extra_gains_reduce_relevance(self):
        broad = event("broad-candidate", {
            "system-design": 1, "unrelated-one": 1,
            "unrelated-two": 1, "unrelated-three": 1,
        })
        focused = event("focused-candidate")
        result = self.run_engine([broad, focused])
        ranked = by_id(result)
        self.assertEqual(ids(result), ["focused-candidate", "broad-candidate"])
        self.assertEqual(normalized(ranked["focused-candidate"], "career_relevance"), 1)
        self.assertEqual(normalized(ranked["broad-candidate"], "career_relevance"), 0.25)
        self.assertEqual(ranked["broad-candidate"]["simulation"]["total_gap_reduction"], 1)
        self.assertEqual(sum(change["actual_gain"] for change in
                             ranked["broad-candidate"]["simulation"]["skill_impact"]), 4)

    def test_top_n_uses_all_candidate_normalizers_and_preserves_scores(self):
        catalog = [
            event("critical-shortlist"),
            event("broad-maximum", {"public-speaking": 2, "writing": 4}),
            event("speaking-small", {"public-speaking": 1}),
            event("writing-small", {"writing": 1}),
        ]
        role_profiles = profiles({"system-design": 4, "public-speaking": 2, "writing": 4})
        one = self.run_engine(catalog, role_profiles=role_profiles, top_n=1)
        three = self.run_engine(catalog, role_profiles=role_profiles, top_n=3)
        self.assertEqual(one["candidate_count"], 4)
        self.assertEqual(one["recommendation_count"], 1)
        self.assertEqual(three["recommendation_count"], 3)
        self.assertEqual(ids(one), ["critical-shortlist"])
        self.assertEqual(one["recommendations"], three["recommendations"][:1])
        self.assertEqual(normalized(one["recommendations"][0], "gap_reduction"), 1 / 6)
        self.assertEqual(normalized(one["recommendations"][0], "effort_efficiency"), 1 / 6)

    def test_event_profile_and_history_order_do_not_change_output_or_precision(self):
        catalog = [event("zulu"), event("alpha"), event("middle", {"public-speaking": 1})]
        history = [
            participation("record-z", "middle", "no_show"),
            participation("record-a", "middle", "dropped", feedback_rating=4),
            participation("record-m", "alpha", "declined"),
        ]
        first = self.run_engine(catalog, history)
        reversed_result = self.run_engine(list(reversed(catalog)), list(reversed(history)),
                                          role_profiles=list(reversed(profiles())))
        self.assertEqual(first, reversed_result)
        self.assertEqual(first, self.run_engine(catalog, history))
        self.assertEqual([item["rank"] for item in first["recommendations"]], [1, 2, 3])

    def test_final_unrounded_score_precedes_all_tie_breakers(self):
        catalog = [event("a-slower", duration_hours=4.000001), event("z-faster", duration_hours=4)]
        result = self.run_engine(catalog)
        self.assertEqual(ids(result), ["z-faster", "a-slower"])
        first, second = result["recommendations"]
        self.assertGreater(first["score"], second["score"])
        self.assertEqual(round(first["score"], 6), round(second["score"], 6))

    def test_tie_prefers_critical_gap_reduction_before_total_gap(self):
        catalog = [event("z-critical"), event("a-noncritical", {"public-speaking": 2})]
        result = self.run_engine(catalog, config=TIE_CONFIG)
        self.assertEqual(ids(result), ["z-critical", "a-noncritical"])
        self.assertEqual(result["recommendations"][0]["score"], result["recommendations"][1]["score"])

    def test_tie_prefers_total_gap_reduction_after_equal_critical_impact(self):
        catalog = [event("a-single"), event("z-multiple", {"system-design": 1, "public-speaking": 1})]
        result = self.run_engine(catalog, config=TIE_CONFIG)
        self.assertEqual(ids(result), ["z-multiple", "a-single"])

    def test_tie_prefers_earlier_availability_before_shorter_duration(self):
        catalog = [
            event("a-later-shorter", format="online", upcoming_sessions=["2026-10-03"], duration_hours=1),
            event("z-earlier-longer", format="online", upcoming_sessions=["2026-10-02"], duration_hours=20),
        ]
        result = self.run_engine(catalog, config=TIE_CONFIG)
        self.assertEqual(ids(result), ["z-earlier-longer", "a-later-shorter"])

    def test_tie_self_paced_is_available_today(self):
        catalog = [event("z-self-paced"), event("a-tomorrow", format="online", upcoming_sessions=["2026-10-02"])]
        result = self.run_engine(catalog, config=TIE_CONFIG)
        self.assertEqual(ids(result), ["z-self-paced", "a-tomorrow"])

    def test_tie_prefers_shorter_duration_after_equal_impact_and_availability(self):
        catalog = [event("a-long", duration_hours=8), event("z-short", duration_hours=2)]
        self.assertEqual(ids(self.run_engine(catalog, config=TIE_CONFIG)), ["z-short", "a-long"])

    def test_tie_unknown_or_invalid_duration_sorts_after_valid_duration(self):
        for duration in (None, 0, -2, "unknown", True, float("inf"), float("nan")):
            with self.subTest(duration=duration):
                catalog = [event("a-invalid", duration_hours=duration), event("z-valid", duration_hours=4)]
                result = self.run_engine(catalog, config=TIE_CONFIG)
                self.assertEqual(ids(result), ["z-valid", "a-invalid"])
                self.assertEqual(normalized(by_id(result)["a-invalid"], "effort_efficiency"), 0)
                # Invalid user-supplied numbers must not leak NaN/Infinity into a JSON response.
                json.dumps(result, allow_nan=False)

    def test_tie_missing_duration_is_safe(self):
        missing = event("a-missing")
        del missing["duration_hours"]
        result = self.run_engine([missing, event("z-valid")], config=TIE_CONFIG)
        self.assertEqual(ids(result), ["z-valid", "a-missing"])

    def test_full_tie_uses_event_id_ascending(self):
        catalog = [event("z-event"), event("a-event"), event("m-event")]
        self.assertEqual(ids(self.run_engine(catalog)), ["a-event", "m-event", "z-event"])

    def test_default_top_three_and_fewer_candidates_have_no_padding(self):
        for count in (1, 2, 3, 5):
            with self.subTest(candidate_count=count):
                result = self.run_engine([event("candidate-{}".format(index)) for index in range(count)])
                self.assertEqual(result["candidate_count"], count)
                self.assertEqual(result["recommendation_count"], min(3, count))
                self.assertEqual(len(result["recommendations"]), min(3, count))
                self.assertEqual(result["status"], "ok")
                self.assertIsNone(result["blocked_summary"])

    def test_empty_catalog_has_explained_zero_result_and_uncovered_gaps(self):
        result = self.run_engine([])
        self.assertEqual(result["status"], "no_eligible_recommendations")
        self.assertEqual(result["recommendations"], [])
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["recommendation_count"], 0)
        blocked = result["blocked_summary"]
        self.assertEqual(blocked["event_rejections"], [])
        self.assertEqual(blocked["useful_blocked_events"], [])
        self.assertEqual(blocked["uncovered_target_gaps"], result["skill_gaps"])

    def test_no_candidates_preserve_multiple_reasons_and_useful_blocked_evidence(self):
        catalog = [
            event("already-done"),
            event("wrong-audience", target_roles=["Unrelated occupation"], target_grades=["Lead"]),
        ]
        history = [participation("completed-attempt", "already-done", "completed")]
        result = self.run_engine(catalog, history)
        self.assertEqual(result["status"], "no_eligible_recommendations")
        blocked = result["blocked_summary"]
        self.assertEqual(blocked["rejection_counts"]["ALREADY_COMPLETED"], 1)
        self.assertEqual(blocked["rejection_counts"]["ROLE_MISMATCH"], 1)
        self.assertEqual(blocked["rejection_counts"]["GRADE_MISMATCH"], 1)
        rejected = {item["event_id"]: set(item["rejection_codes"]) for item in blocked["event_rejections"]}
        self.assertEqual(rejected["already-done"], {"ALREADY_COMPLETED"})
        self.assertEqual(rejected["wrong-audience"], {"ROLE_MISMATCH", "GRADE_MISMATCH"})
        useful = {item["event_id"]: item for item in blocked["useful_blocked_events"]}
        self.assertEqual(set(useful), {"already-done", "wrong-audience"})
        self.assertEqual(useful["already-done"]["critical_gap_reduction"], 1)
        self.assertEqual(useful["already-done"]["total_gap_reduction"], 1)
        self.assertEqual([gap["skill_id"] for gap in blocked["uncovered_target_gaps"]], ["public-speaking"])

    def test_mandatory_only_catalog_does_not_claim_voluntary_gap_coverage(self):
        result = self.run_engine([event("mandatory-learning", mandatory=True)])
        self.assertEqual(result["status"], "no_eligible_recommendations")
        blocked = result["blocked_summary"]
        self.assertEqual(blocked["rejection_counts"]["MANDATORY"], 1)
        self.assertEqual(blocked["uncovered_target_gaps"], result["skill_gaps"])
        self.assertEqual(blocked["useful_blocked_events"], [])

    def test_lead_without_goal_keeps_distinct_no_next_grade_state(self):
        result = self.run_engine([event("lead-session", target_grades=["Lead"])], person=employee(grade="Lead"))
        self.assertEqual(result["status"], "no_next_grade")
        self.assertIsNone(result["target"])
        self.assertIsNone(result["career_readiness"])
        self.assertEqual(result["skill_gaps"], [])
        self.assertEqual(result["recommendations"], [])
        self.assertEqual(result["blocked_summary"]["rejection_counts"]["NO_CAREER_TARGET"], 1)

    def test_lead_with_explicit_transition_gets_target_role_recommendation(self):
        person = employee(grade="Lead", career_goal={"target_role": DESTINATION, "target_grade": "Lead"})
        result = self.run_engine([event("transition-session", target_roles=[DESTINATION], target_grades=["Lead"])], person=person)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["target"]["role"], DESTINATION)
        self.assertEqual(result["recommendations"][0]["evidence"]["audience_match"], "target_role")
        self.assertEqual(result["recommendations"][0]["evidence"]["attained_grade"], "Lead")

    def test_satisfied_target_does_not_fabricate_recommendations(self):
        result = self.run_engine(person=employee(skills={"system-design": 4, "public-speaking": 2}))
        self.assertEqual(result["status"], "target_satisfied")
        self.assertEqual(result["career_readiness"]["current"], 1)
        self.assertEqual(result["recommendations"], [])
        self.assertEqual(result["blocked_summary"]["uncovered_target_gaps"], [])

    def test_empty_target_requirements_keep_unavailable_readiness_state(self):
        result = self.run_engine(role_profiles=profiles({}, []))
        self.assertEqual(result["status"], "invalid_target_requirements")
        self.assertIsNone(result["career_readiness"]["current"])
        self.assertEqual(result["recommendations"], [])

    def test_factor_breakdown_and_raw_simulation_explain_full_precision_score(self):
        result = self.run_engine()
        item = result["recommendations"][0]
        self.assertEqual(set(item["factors"]), set(vars(DEFAULT_CONFIG.scoring_weights)))
        for name, factor in item["factors"].items():
            with self.subTest(factor=name):
                self.assertIn("raw", factor)
                self.assertEqual(factor["weight"], getattr(DEFAULT_CONFIG.scoring_weights, name))
                self.assertTrue(isfinite(factor["normalized"]))
                self.assertGreaterEqual(factor["normalized"], 0)
                self.assertLessEqual(factor["normalized"], 1)
                self.assertAlmostEqual(factor["contribution"], factor["normalized"] * factor["weight"])
        self.assertAlmostEqual(item["score"], fsum(factor["contribution"] for factor in item["factors"].values()))
        self.assertTrue(item["scoring_evidence"])
        self.assertEqual(item["simulation"]["critical_gap_before"], 2)
        self.assertEqual(item["simulation"]["critical_gap_after"], 1)
        self.assertEqual(item["simulation"]["total_gap_before"], 4)
        self.assertEqual(item["simulation"]["total_gap_after"], 3)
        self.assertAlmostEqual(item["simulation"]["readiness_before"], 0.4)
        self.assertAlmostEqual(item["simulation"]["readiness_after"], 0.6)
        self.assertAlmostEqual(item["simulation"]["readiness_delta"], 0.2)
        self.assertEqual(item["evidence"]["audience_match"], "current_role")
        self.assertTrue(item["evidence"]["availability"]["self_paced"])
        json.dumps(result, allow_nan=False)

    def test_default_history_evidence_is_aggregate_and_record_detail_is_opt_in(self):
        catalog = [event("private-history-candidate")]
        history = [participation("private-attempt-id", "private-history-candidate", "dropped",
                                 feedback_rating=3, score=40)]
        default = self.run_engine(catalog, history)
        detailed = self.run_engine(catalog, history, include_history_records=True)
        ordinary_item = default["recommendations"][0]
        detailed_item = detailed["recommendations"][0]
        self.assertNotIn("record_evidence", ordinary_item["history_signals"])
        self.assertTrue(detailed_item["history_signals"]["record_evidence"])
        self.assertIn("evidence", ordinary_item["history_signals"])
        self.assertEqual(ordinary_item["score"], detailed_item["score"])
        self.assertEqual(ordinary_item["factors"], detailed_item["factors"])

    def test_future_outcomes_do_not_change_scores_at_official_snapshot(self):
        catalog = [event("future-attempt-candidate")]
        baseline = self.run_engine(catalog)
        future = self.run_engine(catalog, [
            participation("future-no-show", "future-attempt-candidate", date="2026-10-02"),
            participation("future-completion", "future-attempt-candidate", "completed",
                          date="2026-09-01", completed_at="2026-10-02T03:00:00Z", feedback_rating=5, score=100),
        ])
        self.assertEqual(ids(future), ids(baseline))
        self.assertEqual(future["recommendations"][0]["factors"], baseline["recommendations"][0]["factors"])
        self.assertEqual(future["recommendations"][0]["score"], baseline["recommendations"][0]["score"])

    def test_unseen_assignment_source_does_not_crash_recommendation(self):
        result = self.run_engine([event("unseen-source-event")], [
            participation("novel-source", "unseen-source-event", "dropped", assigned_by="jury-import"),
        ])
        self.assertEqual(result["status"], "ok")
        self.assertTrue(isfinite(result["recommendations"][0]["score"]))

    def test_orchestration_preserves_career_state_and_all_inputs(self):
        person = employee()
        role_profiles = profiles()
        catalog = [event("candidate"), event("old-course")]
        history = [participation("old-completion", "old-course", "completed", date="2026-09-01")]
        before = deepcopy((person, role_profiles, catalog, history))
        state = build_career_state(person, role_profiles, catalog, history, as_of=AS_OF)
        result = self.run_engine(catalog, history, person, role_profiles)
        self.assertEqual((person, role_profiles, catalog, history), before)
        self.assertEqual(result["career_state"], state)
        self.assertEqual(result["career_readiness"], state["career_readiness"])
        self.assertEqual(result["skill_gaps"], state["skill_gaps"])
        self.assertEqual(result["target"], state["target"])
        self.assertEqual(result["employee_id"], PERSON_ID)
        self.assertEqual(result["as_of"], AS_OF)
        # A caller editing a result must not edit its review baseline or catalog.
        result["recommendations"][0]["simulation"]["simulated_skills_after"]["system-design"] = 99
        self.assertEqual((person, role_profiles, catalog, history), before)

    def test_invalid_top_n_is_a_structured_boundary_error(self):
        for value in (None, 0, -1, 4, 1.0, "3", True, False):
            with self.subTest(top_n=value):
                with self.assertRaises(RecommendationInputError) as captured:
                    self.run_engine(top_n=value)
                self.assertEqual(captured.exception.code, "invalid_top_n")


if __name__ == "__main__":
    unittest.main()
