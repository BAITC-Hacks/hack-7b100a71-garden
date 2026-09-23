"""Explainable admission checks for synthetic, previously unseen profiles."""

from copy import deepcopy
from dataclasses import replace
from datetime import date
import unittest

from backend.recommendation.career import build_career_state
from backend.recommendation.config import DEFAULT_CONFIG
from backend.recommendation.contracts import RecommendationInputError
from backend.recommendation.eligibility import evaluate_catalog, evaluate_event


AS_OF = "2026-10-01"
CURRENT_ROLE = "Platform Researcher"
DESTINATION_ROLE = "Service Designer"


def profiles():
    return [
        {
            "role": role,
            "grade": grade,
            "required_skills": {"systems": 4, "writing": 2},
            "critical_skills": ["systems"],
        }
        for role in (CURRENT_ROLE, DESTINATION_ROLE)
        for grade in DEFAULT_CONFIG.grades
    ]


def employee(**changes):
    value = {
        "employee_id": "unseen-person-42",
        "role": CURRENT_ROLE,
        "grade": "Middle",
        "career_goal": None,
        "skills": {"systems": 1, "writing": 0},
        "last_review_date": "2026-08-01",
    }
    value.update(changes)
    return value


def event(event_id="unseen-workshop", **changes):
    value = {
        "event_id": event_id,
        "title": "Systems Workshop",
        "mandatory": False,
        "format": "self_paced",
        "target_roles": [CURRENT_ROLE],
        "target_grades": ["Middle"],
        "prerequisites": {},
        "upcoming_sessions": [],
        "develops_skills": [{"skill_id": "systems", "gain": 1, "max_level": 5}],
    }
    value.update(changes)
    return value


def participation(record_id="old-attempt", **changes):
    value = {
        "record_id": record_id,
        "employee_id": "unseen-person-42",
        "event_id": "unseen-workshop",
        "date": "2026-07-01",
        "status": "completed",
    }
    value.update(changes)
    return value


def reason_codes(result):
    return {reason["code"] for reason in result["rejection_reasons"]}


class EligibilityTests(unittest.TestCase):
    def prepare(self, person=None, candidate=None, history=None, extra_events=None,
                config=DEFAULT_CONFIG):
        person = employee() if person is None else person
        candidate = event() if candidate is None else candidate
        history = [] if history is None else history
        catalog = [candidate] + ([] if extra_events is None else extra_events)
        available_profiles = profiles()
        state = build_career_state(
            person, available_profiles, catalog, history, as_of=AS_OF, config=config,
        )
        target = state["target"]
        target_profile = next((
            profile for profile in available_profiles
            if target and (profile["role"], profile["grade"]) == (target["role"], target["grade"])
        ), None)
        return person, state, target_profile, candidate, history

    def evaluate(self, person=None, candidate=None, history=None, extra_events=None,
                 config=DEFAULT_CONFIG):
        values = self.prepare(person, candidate, history, extra_events, config)
        return evaluate_event(*values, as_of=AS_OF, config=config)

    def assert_rejected(self, result, expected_codes):
        self.assertFalse(result["eligible"])
        self.assertEqual(reason_codes(result), set(expected_codes))
        for reason in result["rejection_reasons"]:
            self.assertIsInstance(reason["message"], str)
            self.assertTrue(reason["message"].strip())

    def test_current_role_and_attained_grade_admit_unseen_employee(self):
        result = self.evaluate()
        self.assertTrue(result["eligible"])
        self.assertEqual(result["event_id"], "unseen-workshop")
        self.assertEqual(result["rejection_reasons"], [])
        evidence = result["evidence"]
        self.assertEqual(evidence["audience_match"], "current_role")
        self.assertEqual(evidence["current_role"], CURRENT_ROLE)
        self.assertEqual(evidence["target_role"], CURRENT_ROLE)
        self.assertEqual(evidence["target_grade"], "Senior")
        self.assertEqual(evidence["attained_grade"], "Middle")
        self.assertEqual(evidence["matched_current_grade"], "Middle")
        self.assertFalse(evidence["skills_are_estimated"])
        self.assertGreater(result["simulation"]["total_gap_reduction"], 0)

    def test_mandatory_event_is_rejected_even_with_useful_gain(self):
        result = self.evaluate(candidate=event(mandatory=True))
        self.assert_rejected(result, {"MANDATORY"})
        self.assertGreater(result["simulation"]["total_gap_reduction"], 0)

    def test_explicit_destination_role_admission_is_identified(self):
        person = employee(career_goal={"target_role": DESTINATION_ROLE, "target_grade": "Middle"})
        result = self.evaluate(person=person, candidate=event(target_roles=[DESTINATION_ROLE]))
        self.assertTrue(result["eligible"])
        self.assertEqual(result["evidence"]["audience_match"], "target_role")
        self.assertEqual(result["evidence"]["current_role"], CURRENT_ROLE)
        self.assertEqual(result["evidence"]["target_role"], DESTINATION_ROLE)

    def test_both_matching_roles_are_distinct_from_target_only(self):
        person = employee(career_goal={"target_role": DESTINATION_ROLE, "target_grade": "Senior"})
        result = self.evaluate(person=person, candidate=event(target_roles=[CURRENT_ROLE, DESTINATION_ROLE]))
        self.assertTrue(result["eligible"])
        self.assertEqual(result["evidence"]["audience_match"], "both")

    def test_explicit_same_role_goal_can_match_both_but_inferred_goal_does_not(self):
        person = employee(career_goal={"target_role": CURRENT_ROLE, "target_grade": "Senior"})
        self.assertEqual(self.evaluate(person=person)["evidence"]["audience_match"], "both")
        self.assertEqual(self.evaluate()["evidence"]["audience_match"], "current_role")

    def test_other_role_is_not_admitted_without_explicit_destination_goal(self):
        result = self.evaluate(candidate=event(target_roles=[DESTINATION_ROLE]))
        self.assert_rejected(result, {"ROLE_MISMATCH"})
        self.assertIsNone(result["evidence"]["audience_match"])

    def test_destination_grade_does_not_satisfy_current_admission(self):
        result = self.evaluate(candidate=event(target_grades=["Senior"]))
        self.assert_rejected(result, {"GRADE_MISMATCH"})
        self.assertEqual(result["evidence"]["target_grade"], "Senior")
        self.assertEqual(result["evidence"]["attained_grade"], "Middle")
        self.assertIsNone(result["evidence"]["matched_current_grade"])

    def test_every_prerequisite_is_reported_including_missing_skill_zero(self):
        result = self.evaluate(candidate=event(prerequisites={"systems": 1, "unseen-prerequisite": 2}))
        self.assert_rejected(result, {"PREREQUISITE_NOT_MET"})
        checks = {check["skill_id"]: check for check in result["evidence"]["prerequisite_checks"]}
        self.assertEqual(checks, {
            "systems": {"skill_id": "systems", "current": 1, "required": 1, "met": True},
            "unseen-prerequisite": {"skill_id": "unseen-prerequisite", "current": 0, "required": 2, "met": False},
        })

    def test_all_satisfied_prerequisites_allow_event(self):
        result = self.evaluate(candidate=event(prerequisites={"systems": 1, "writing": 0}))
        self.assertTrue(result["eligible"])
        self.assertTrue(all(check["met"] for check in result["evidence"]["prerequisite_checks"]))

    def test_reconstructed_mandatory_history_can_unlock_prerequisite(self):
        candidate = event(prerequisites={"systems": 2})
        bootstrap = event("onboarding-unseen", mandatory=True)
        history = [participation("bootstrap-completion", event_id=bootstrap["event_id"], date="2026-09-01")]
        self.assert_rejected(self.evaluate(candidate=candidate), {"PREREQUISITE_NOT_MET"})
        result = self.evaluate(candidate=candidate, history=history, extra_events=[bootstrap])
        self.assertTrue(result["eligible"])
        self.assertEqual(result["evidence"]["prerequisite_checks"], [
            {"skill_id": "systems", "current": 2, "required": 2, "met": True},
        ])
        self.assertTrue(result["evidence"]["skills_are_estimated"])

    def test_completed_voluntary_event_blocks_even_before_or_on_review(self):
        for when in ("2026-07-01", "2026-08-01", "2026-09-01"):
            with self.subTest(date=when):
                result = self.evaluate(history=[participation(date=when)])
                self.assert_rejected(result, {"ALREADY_COMPLETED"})
                self.assertEqual(result["evidence"]["history"]["completed_record_ids"], ["old-attempt"])

    def test_recurring_club_completion_does_not_block(self):
        result = self.evaluate(candidate=event("EV_036"), history=[participation(event_id="EV_036")])
        self.assertTrue(result["eligible"])
        self.assertTrue(result["evidence"]["history"]["recurring_exception"])
        self.assertEqual(result["evidence"]["history"]["completed_record_ids"], ["old-attempt"])

    def test_recurring_event_policy_can_be_reconfigured_for_unseen_id(self):
        config = replace(DEFAULT_CONFIG, recurring_event_ids=("new-recurring-event",))
        result = self.evaluate(
            candidate=event("new-recurring-event"),
            history=[participation(event_id="new-recurring-event")], config=config,
        )
        self.assertTrue(result["eligible"])
        old_exception = self.evaluate(
            candidate=event("EV_036"), history=[participation(event_id="EV_036")], config=config,
        )
        self.assert_rejected(old_exception, {"ALREADY_COMPLETED"})
        self.assertFalse(old_exception["evidence"]["history"]["recurring_exception"])

    def test_completed_mandatory_history_is_not_retroactively_flagged_as_voluntary_repeat(self):
        result = self.evaluate(candidate=event(mandatory=True), history=[participation()])
        self.assert_rejected(result, {"MANDATORY"})
        self.assertEqual(result["evidence"]["history"]["completed_record_ids"], ["old-attempt"])

    def test_any_active_attempt_blocks_even_with_a_separate_later_completion(self):
        history = [
            participation("active-a", status="in_progress"),
            participation("completed-b", date="2026-07-02"),
            participation("active-c", status="in_progress", date="2026-07-03"),
        ]
        result = self.evaluate(history=history)
        self.assert_rejected(result, {"ALREADY_COMPLETED", "ALREADY_IN_PROGRESS"})
        evidence = result["evidence"]["history"]
        self.assertEqual(evidence["completed_record_ids"], ["completed-b"])
        self.assertEqual(evidence["in_progress_record_ids"], ["active-a", "active-c"])
        recurring = self.evaluate(
            candidate=event("EV_036"),
            history=[dict(row, event_id="EV_036") for row in history],
        )
        self.assert_rejected(recurring, {"ALREADY_IN_PROGRESS"})

    def test_negative_history_never_permanently_bans_participation(self):
        history = [participation("attempt-" + status, status=status)
                   for status in ("no_show", "dropped", "declined")]
        result = self.evaluate(history=history)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["evidence"]["history"]["completed_record_ids"], [])
        self.assertEqual(result["evidence"]["history"]["in_progress_record_ids"], [])

    def test_other_employee_completions_and_other_event_participations_do_not_block(self):
        unrelated = event("another-event", develops_skills=[])
        history = [
            participation("someone-else", employee_id="different-person"),
            participation("other-event-active", event_id=unrelated["event_id"], status="in_progress"),
        ]
        result = self.evaluate(history=history, extra_events=[unrelated])
        self.assertTrue(result["eligible"])
        self.assertEqual(result["evidence"]["history"]["completed_record_ids"], [])
        self.assertEqual(result["evidence"]["history"]["in_progress_record_ids"], [])

    def test_future_participations_and_future_actual_completion_do_not_block(self):
        history = [
            participation("future-completed", date="2026-10-02"),
            participation("future-active", date="2026-10-02", status="in_progress"),
            participation("future-completion-time", date="2026-09-01", completed_at="2026-10-02T00:00:00+06:00"),
        ]
        result = self.evaluate(history=history)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["evidence"]["history"]["ignored_future_record_ids"], [
            "future-active", "future-completed", "future-completion-time",
        ])
        self.assertEqual(result["evidence"]["history"]["completed_record_ids"], [])

    def test_completion_uses_stated_snapshot_day_including_end_of_day(self):
        result = self.evaluate(history=[participation(
            completed_at="2026-10-01T23:59:59-06:00",
        )])
        self.assert_rejected(result, {"ALREADY_COMPLETED"})
        self.assertEqual(result["evidence"]["history"]["ignored_future_record_ids"], [])

    def test_identical_history_duplicates_are_counted_once_and_conflicts_raise(self):
        values = self.prepare()
        record = participation()
        duplicate_result = evaluate_event(*values[:-1], [record, deepcopy(record)], as_of=AS_OF)
        self.assertEqual(duplicate_result["evidence"]["history"]["completed_record_ids"], ["old-attempt"])
        with self.assertRaises(RecommendationInputError):
            evaluate_event(*values[:-1], [record, participation(status="in_progress")], as_of=AS_OF)

    def test_self_paced_available_without_sessions(self):
        result = self.evaluate()
        availability = result["evidence"]["availability"]
        self.assertTrue(availability["self_paced"])
        self.assertTrue(availability["available"])
        self.assertEqual(availability["format"], "self_paced")
        self.assertIsNone(availability["next_session_date"])
        self.assertEqual(availability["days_until_next_session"], 0)
        self.assertEqual(availability["valid_session_dates"], [])

    def test_scheduled_sessions_are_sorted_deduplicated_and_include_snapshot(self):
        candidate = event(format="online", upcoming_sessions=[
            "2026-11-01", "2026-09-30", "2026-10-01", "2026-10-09", "2026-10-01",
        ])
        result = self.evaluate(candidate=candidate)
        self.assertTrue(result["eligible"])
        availability = result["evidence"]["availability"]
        self.assertFalse(availability["self_paced"])
        self.assertEqual(availability["next_session_date"], AS_OF)
        self.assertEqual(availability["days_until_next_session"], 0)
        self.assertEqual(availability["valid_session_dates"], [AS_OF, "2026-10-09", "2026-11-01"])

    def test_future_scheduled_event_returns_exact_wait_from_snapshot(self):
        result = self.evaluate(candidate=event(format="offline", upcoming_sessions=["2026-10-09"]))
        self.assertTrue(result["eligible"])
        self.assertEqual(result["evidence"]["availability"]["next_session_date"], "2026-10-09")
        self.assertEqual(result["evidence"]["availability"]["days_until_next_session"], 8)

    def test_scheduled_event_with_no_future_session_is_rejected(self):
        for sessions in ([], ["2026-09-30", "2026-01-01"]):
            with self.subTest(sessions=sessions):
                result = self.evaluate(candidate=event(format="online", upcoming_sessions=sessions))
                self.assert_rejected(result, {"NO_UPCOMING_SESSION"})
                availability = result["evidence"]["availability"]
                self.assertFalse(availability["available"])
                self.assertIsNone(availability["next_session_date"])
                self.assertIsNone(availability["days_until_next_session"])

    def test_irrelevant_skill_increase_is_not_useful_destination_impact(self):
        candidate = event(develops_skills=[{"skill_id": "unrelated", "gain": 3, "max_level": 5}])
        result = self.evaluate(candidate=candidate)
        self.assert_rejected(result, {"NO_TARGET_GAP_IMPACT"})
        self.assertEqual(result["simulation"]["total_gap_reduction"], 0)
        self.assertEqual(result["simulation"]["readiness_delta"], 0)

    def test_relevant_skill_at_or_above_event_cap_has_no_useful_impact(self):
        for current in (2, 3):
            with self.subTest(current=current):
                candidate = event(develops_skills=[{"skill_id": "systems", "gain": 2, "max_level": 2}])
                result = self.evaluate(person=employee(skills={"systems": current}), candidate=candidate)
                self.assert_rejected(result, {"NO_TARGET_GAP_IMPACT"})
                self.assertEqual(result["simulation"]["total_gap_reduction"], 0)
                self.assertEqual(result["simulation"]["readiness_delta"], 0)

    def test_event_improving_already_satisfied_requirement_is_not_useful(self):
        result = self.evaluate(person=employee(skills={"systems": 4, "writing": 0}))
        self.assert_rejected(result, {"NO_TARGET_GAP_IMPACT"})
        self.assertEqual(result["simulation"]["total_gap_reduction"], 0)

    def test_all_independent_rejections_accumulate_without_early_return(self):
        candidate = event(
            mandatory=True, target_roles=["Other Role"], target_grades=["Lead"],
            prerequisites={"unseen-prerequisite": 4}, format="online",
            develops_skills=[{"skill_id": "unrelated", "gain": 1, "max_level": 5}],
        )
        history = [participation(), participation("active", status="in_progress")]
        result = self.evaluate(candidate=candidate, history=history)
        self.assert_rejected(result, {
            "MANDATORY", "ROLE_MISMATCH", "GRADE_MISMATCH", "PREREQUISITE_NOT_MET",
            "ALREADY_IN_PROGRESS", "NO_TARGET_GAP_IMPACT", "NO_UPCOMING_SESSION",
        })
        self.assertIsNotNone(result["simulation"])

    def test_lead_without_goal_has_explicit_no_target_reason_and_no_simulation(self):
        result = self.evaluate(person=employee(grade="Lead"), candidate=event(target_grades=["Lead"]))
        self.assert_rejected(result, {"NO_CAREER_TARGET"})
        self.assertIsNone(result["simulation"])
        self.assertIsNone(result["evidence"]["target_role"])
        self.assertIsNone(result["evidence"]["target_grade"])
        self.assertEqual(result["evidence"]["audience_match"], "current_role")

    def test_lead_with_explicit_transition_can_receive_eligible_activity(self):
        person = employee(grade="Lead", career_goal={"target_role": DESTINATION_ROLE, "target_grade": "Lead"})
        result = self.evaluate(person=person, candidate=event(target_roles=[DESTINATION_ROLE], target_grades=["Lead"]))
        self.assertTrue(result["eligible"])
        self.assertEqual(result["evidence"]["audience_match"], "target_role")
        self.assertEqual(result["evidence"]["matched_current_grade"], "Lead")

    def test_event_evaluation_is_idempotent_and_does_not_mutate_inputs(self):
        values = self.prepare(history=[participation("negative", status="dropped")])
        before = deepcopy(values)
        first = evaluate_event(*values, as_of=AS_OF)
        second = evaluate_event(*values, as_of=date(2026, 10, 1))
        self.assertEqual(first, second)
        self.assertEqual(values, before)
        first["evidence"]["prerequisite_checks"].append({"skill_id": "mutated-output"})
        self.assertEqual(values, before)
        self.assertEqual(evaluate_event(*values, as_of=AS_OF), second)

    def test_mismatched_career_state_employee_snapshot_and_profile_are_rejected(self):
        original = self.prepare()
        for index, field, value in (
            (1, "employee_id", "someone-else"),
            (1, "as_of", "2026-09-30"),
            (2, "role", DESTINATION_ROLE),
            (2, "grade", "Lead"),
        ):
            with self.subTest(index=index, field=field):
                values = deepcopy(original)
                values[index][field] = value
                with self.assertRaises(RecommendationInputError):
                    evaluate_event(*values, as_of=AS_OF)


class CatalogEligibilityTests(unittest.TestCase):
    def test_catalog_returns_all_decisions_ordered_by_id_not_ranked(self):
        person = employee()
        catalog = [event("z-useful"), event("m-rejected", mandatory=True), event("a-useful")]
        available_profiles = profiles()
        state = build_career_state(person, available_profiles, catalog, [], as_of=AS_OF)
        before = deepcopy((person, state, available_profiles, catalog))
        result = evaluate_catalog(person, state, available_profiles, catalog, [], as_of=AS_OF)
        self.assertEqual(result["employee_id"], person["employee_id"])
        self.assertEqual(result["as_of"], AS_OF)
        self.assertEqual(result["target"], state["target"])
        self.assertEqual((result["event_count"], result["eligible_count"], result["rejected_count"]), (3, 2, 1))
        self.assertEqual([item["event_id"] for item in result["eligible_candidates"]], ["a-useful", "z-useful"])
        self.assertEqual([item["event_id"] for item in result["rejected_events"]], ["m-rejected"])
        self.assertEqual((person, state, available_profiles, catalog), before)
        reordered = evaluate_catalog(person, state, list(reversed(available_profiles)), list(reversed(catalog)), [], as_of=AS_OF)
        self.assertEqual(result, reordered)
        self.assertNotIn("score", result["eligible_candidates"][0])

    def test_empty_catalog_and_no_target_catalog_are_valid_results(self):
        person = employee(grade="Lead")
        available_profiles = profiles()
        state = build_career_state(person, available_profiles, [], [], as_of=AS_OF)
        empty = evaluate_catalog(person, state, available_profiles, [], [], as_of=AS_OF)
        self.assertEqual(empty["event_count"], 0)
        self.assertEqual(empty["eligible_candidates"], [])
        self.assertEqual(empty["rejected_events"], [])
        result = evaluate_catalog(person, state, available_profiles, [event(target_grades=["Lead"])], [], as_of=AS_OF)
        self.assertEqual(result["eligible_count"], 0)
        self.assertEqual(result["rejected_count"], 1)
        self.assertEqual(reason_codes(result["rejected_events"][0]), {"NO_CAREER_TARGET"})

    def test_history_order_and_repeated_catalog_evaluation_do_not_change_results(self):
        person = employee()
        catalog = [event("EV_036"), event()]
        available_profiles = profiles()
        history = [participation("earlier"), participation("active", status="in_progress", date="2026-08-02")]
        state = build_career_state(person, available_profiles, catalog, history, as_of=AS_OF)
        first = evaluate_catalog(person, state, available_profiles, catalog, history, as_of=AS_OF)
        second = evaluate_catalog(person, state, available_profiles, catalog, list(reversed(history)), as_of=AS_OF)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
