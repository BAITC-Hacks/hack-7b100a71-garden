"""Hand-calculated preference signals and robust optional feedback handling."""

from copy import deepcopy
from dataclasses import replace
from datetime import date
import json
import unittest

from backend.recommendation.config import DEFAULT_CONFIG
from backend.recommendation.contracts import RecommendationInputError
from backend.recommendation.history import calculate_history_signals


SNAPSHOT = "2026-10-01"
EMPLOYEE_ID = "new-person-history-42"


def event(event_id="new-candidate", skills=("systems",), **changes):
    value = {
        "event_id": event_id, "type": "course", "format": "self_paced", "mandatory": False,
        "develops_skills": [{"skill_id": skill, "gain": 1, "max_level": 5} for skill in skills],
    }
    value.update(changes)
    return value


def record(record_id="attempt-1", **changes):
    value = {
        "record_id": record_id, "employee_id": EMPLOYEE_ID,
        "event_id": "new-history-event", "date": SNAPSHOT,
        "status": "completed", "assigned_by": "self", "feedback_rating": "", "score": "",
    }
    value.update(changes)
    return value


class HistorySignalTests(unittest.TestCase):
    def calculate(self, records=None, candidate=None, historical=None, **kwargs):
        candidate = event() if candidate is None else candidate
        historical = event("new-history-event") if historical is None else historical
        return calculate_history_signals(
            EMPLOYEE_ID, candidate, [candidate, historical], [] if records is None else records,
            as_of=kwargs.pop("as_of", SNAPSHOT), **kwargs,
        )

    def test_cold_start_is_neutral_and_exposes_no_private_records(self):
        result = self.calculate()
        self.assertEqual(result["compatibility"], 0.5)
        self.assertEqual(result["feedback_signal"], 0.5)
        self.assertEqual(result["evidence"]["matched_history_count"], 0)
        self.assertEqual(result["evidence"]["effective_history_weight"], 0)
        self.assertNotIn("record_evidence", result)
        self.assertNotIn("record_id", json.dumps(result))

    def test_positive_history_and_both_feedback_signals_have_hand_computed_result(self):
        result = self.calculate([record(score="100", feedback_rating="5")], include_records=True)
        self.assertAlmostEqual(result["compatibility"], 2 / 3)
        self.assertAlmostEqual(result["feedback_signal"], 2 / 3)
        evidence = result["evidence"]
        self.assertEqual(evidence["matched_history_count"], 1)
        self.assertEqual(evidence["effective_history_weight"], 1)
        self.assertEqual(evidence["positive_weight"], 1)
        self.assertEqual(evidence["negative_weight"], 0)
        self.assertEqual(evidence["recent_similar_completions"], 1)
        self.assertEqual(evidence["rating_observation_count"], 1)
        self.assertEqual(evidence["assessment_observation_count"], 1)
        self.assertEqual(evidence["feedback_record_count"], 1)
        self.assertEqual(evidence["effective_feedback_weight"], 1)
        self.assertEqual(result["record_evidence"][0]["record_feedback_signal"], 1)

    def test_three_recent_no_shows_reduce_signal_without_any_veto(self):
        result = self.calculate([record("miss-" + str(i), status="no_show") for i in range(3)])
        self.assertAlmostEqual(result["compatibility"], 0.2)
        self.assertEqual(result["feedback_signal"], 0.5)
        self.assertEqual(result["evidence"]["negative_weight"], 3)
        self.assertEqual(result["evidence"]["positive_weight"], 0)
        self.assertEqual(result["evidence"]["recent_similar_no_shows"], 3)
        self.assertNotIn("eligible", result)
        self.assertNotIn("rejection_reasons", result)

    def test_skill_jaccard_recency_and_assignment_weight_combine_exactly(self):
        candidate = event(skills=("a", "b"))
        historical = event("new-history-event", skills=("b", "c"), format="online")
        result = self.calculate(
            [record(date="2025-10-01", assigned_by="manager")], candidate, historical, include_records=True,
        )
        # Jaccard=1/3; same type=1; same format=0. Similarity=.45.
        # One half-life and manager assignment yield .45 * .5 * .5 = .1125.
        weight = 0.1125
        self.assertAlmostEqual(result["evidence"]["effective_history_weight"], weight)
        self.assertAlmostEqual(result["compatibility"], (1 + weight) / (2 + weight))
        row = result["record_evidence"][0]
        self.assertAlmostEqual(row["skill_similarity"], 1 / 3)
        self.assertAlmostEqual(row["similarity"], 0.45)
        self.assertEqual(row["age_days"], 365)
        self.assertEqual(row["recency"], 0.5)
        self.assertTrue(row["same_type"])
        self.assertFalse(row["same_format"])
        self.assertEqual(result["evidence"]["recent_similar_completions"], 0)

    def test_source_weights_match_official_spellings(self):
        for source, weight in (("self", 1), ("manager", 0.5), ("hr", 0.25)):
            with self.subTest(source=source):
                result = self.calculate([record(assigned_by=source)])
                self.assertEqual(result["evidence"]["effective_history_weight"], weight)
                self.assertAlmostEqual(result["compatibility"], (1 + weight) / (2 + weight))
                self.assertEqual(result["evidence"]["unknown_source_count"], 0)

    def test_unknown_missing_or_malformed_source_uses_neutral_default(self):
        for source in ("team_lead", "HR", None, "", [], {}, 4):
            with self.subTest(source=source):
                result = self.calculate([record(assigned_by=source)], include_records=True)
                self.assertEqual(result["evidence"]["unknown_source_count"], 1)
                self.assertEqual(result["evidence"]["effective_history_weight"], 0.5)
                self.assertFalse(result["record_evidence"][0]["source_is_known"])
                self.assertAlmostEqual(result["compatibility"], 0.6)

    def test_outcome_values_are_applied_without_using_completion_percentage(self):
        outcomes = {"completed": 1, "dropped": 0.25, "no_show": 0, "declined": 0.4}
        for status, outcome in outcomes.items():
            with self.subTest(status=status):
                result = self.calculate([record(status=status, completion_pct="100")])
                self.assertAlmostEqual(result["compatibility"], (1 + outcome) / 3)

    def test_unresolved_and_overdue_records_exclude_both_behavior_and_feedback(self):
        result = self.calculate([
            record("active", status="in_progress", score="100", feedback_rating="5"),
            record("late", status="overdue", score="100", feedback_rating="5"),
        ])
        self.assertEqual(result["compatibility"], 0.5)
        self.assertEqual(result["feedback_signal"], 0.5)
        self.assertEqual(result["evidence"]["excluded_status_count"], 2)
        self.assertEqual(result["evidence"]["assessment_observation_count"], 0)

    def test_mandatory_history_is_excluded_unless_explicitly_configured(self):
        historical = event("new-history-event", mandatory=True)
        rows = [record(assigned_by="hr", score="100", feedback_rating="5")]
        excluded = self.calculate(rows, historical=historical)
        self.assertEqual(excluded["compatibility"], 0.5)
        self.assertEqual(excluded["feedback_signal"], 0.5)
        self.assertEqual(excluded["evidence"]["excluded_mandatory_count"], 1)
        config = replace(DEFAULT_CONFIG, history=replace(DEFAULT_CONFIG.history, include_mandatory=True))
        included = self.calculate(rows, historical=historical, config=config)
        self.assertAlmostEqual(included["compatibility"], 1.25 / 2.25)
        self.assertEqual(included["evidence"]["effective_history_weight"], 0.25)

    def test_empty_skill_sets_have_zero_jaccard_not_perfect_match(self):
        result = self.calculate([record()], event(skills=()), event("new-history-event", skills=()), include_records=True)
        self.assertEqual(result["record_evidence"][0]["skill_similarity"], 0)
        self.assertAlmostEqual(result["evidence"]["effective_history_weight"], 0.4)

    def test_two_missing_types_do_not_create_type_similarity(self):
        candidate, historical = event(skills=()), event("new-history-event", skills=())
        del candidate["type"]
        del historical["type"]
        result = self.calculate([record()], candidate, historical, include_records=True)
        self.assertFalse(result["record_evidence"][0]["same_type"])
        self.assertAlmostEqual(result["evidence"]["effective_history_weight"], 0.15)

    def test_zero_similarity_history_has_no_signal_or_feedback_weight(self):
        historical = event("new-history-event", skills=("unrelated",), type="mentoring", format="offline")
        result = self.calculate([record(score="100", feedback_rating="5")], historical=historical)
        self.assertEqual(result["compatibility"], 0.5)
        self.assertEqual(result["feedback_signal"], 0.5)
        self.assertEqual(result["evidence"]["zero_similarity_count"], 1)
        self.assertEqual(result["evidence"]["matched_history_count"], 0)

    def test_feedback_is_mean_of_present_signals_not_sum_or_missing_zero(self):
        both = self.calculate([record(feedback_rating="5", score="0")], include_records=True)
        self.assertEqual(both["record_evidence"][0]["record_feedback_signal"], 0.5)
        self.assertEqual(both["feedback_signal"], 0.5)
        only_rating = self.calculate([record(feedback_rating="5")])
        self.assertAlmostEqual(only_rating["feedback_signal"], 2 / 3)
        self.assertEqual(only_rating["evidence"]["missing_assessment_count"], 1)
        only_score = self.calculate([record(score="100")])
        self.assertAlmostEqual(only_score["feedback_signal"], 2 / 3)
        self.assertEqual(only_score["evidence"]["missing_rating_count"], 1)

    def test_dropped_feedback_is_used_without_requiring_completion(self):
        result = self.calculate([record(status="dropped", feedback_rating="1")])
        self.assertAlmostEqual(result["compatibility"], 1.25 / 3)
        self.assertAlmostEqual(result["feedback_signal"], 1 / 3)
        self.assertEqual(result["evidence"]["rating_observation_count"], 1)
        self.assertEqual(result["evidence"]["effective_feedback_weight"], 1)

    def test_empty_feedback_cells_add_no_observation(self):
        for value in (None, "", "   "):
            with self.subTest(value=value):
                result = self.calculate([record(feedback_rating=value, score=value)])
                self.assertEqual(result["feedback_signal"], 0.5)
                self.assertEqual(result["evidence"]["effective_feedback_weight"], 0)
                self.assertEqual(result["evidence"]["missing_rating_count"], 1)
                self.assertEqual(result["evidence"]["invalid_rating_count"], 0)

    def test_valid_minimum_feedback_values_are_real_zero_signals(self):
        result = self.calculate([record(feedback_rating=1, score=0)], include_records=True)
        self.assertEqual(result["record_evidence"][0]["rating_signal"], 0)
        self.assertEqual(result["record_evidence"][0]["assessment_signal"], 0)
        self.assertAlmostEqual(result["feedback_signal"], 1 / 3)
        self.assertEqual(result["evidence"]["rating_observation_count"], 1)
        self.assertEqual(result["evidence"]["assessment_observation_count"], 1)

    def test_malformed_optional_numbers_are_skipped_and_counted(self):
        malformed = (True, False, [], {}, "bad", "NaN", "inf", float("nan"), float("inf"))
        for value in malformed:
            with self.subTest(value=value):
                result = self.calculate([record(feedback_rating=value, score=value)])
                self.assertEqual(result["feedback_signal"], 0.5)
                self.assertEqual(result["evidence"]["invalid_rating_count"], 1)
                self.assertEqual(result["evidence"]["invalid_assessment_count"], 1)
                self.assertEqual(result["evidence"]["effective_feedback_weight"], 0)
                json.dumps(result, allow_nan=False)

    def test_out_of_range_rating_does_not_discard_valid_assessment(self):
        for value in (0, 6, "-1", "5.1"):
            with self.subTest(rating=value):
                result = self.calculate([record(feedback_rating=value, score="100")])
                self.assertEqual(result["evidence"]["invalid_rating_count"], 1)
                self.assertEqual(result["evidence"]["assessment_observation_count"], 1)
                self.assertAlmostEqual(result["feedback_signal"], 2 / 3)
        for value in (-1, 101, "100.1"):
            with self.subTest(score=value):
                result = self.calculate([record(feedback_rating="5", score=value)])
                self.assertEqual(result["evidence"]["invalid_assessment_count"], 1)
                self.assertAlmostEqual(result["feedback_signal"], 2 / 3)

    def test_feedback_uses_same_relevance_recency_and_source_weight(self):
        result = self.calculate([record(date="2025-10-01", assigned_by="manager", feedback_rating="5")])
        self.assertEqual(result["evidence"]["effective_feedback_weight"], 0.25)
        self.assertAlmostEqual(result["feedback_signal"], 1.25 / 2.25)

    def test_future_history_and_future_completion_timestamp_are_ignored(self):
        result = self.calculate([
            record("future-participation", date="2026-10-02", status="no_show"),
            record("future-completion", date="2026-09-01", completed_at="2026-10-02T00:00:00+06:00"),
        ])
        self.assertEqual(result["compatibility"], 0.5)
        self.assertEqual(result["evidence"]["ignored_future_count"], 2)
        self.assertEqual(result["evidence"]["matched_history_count"], 0)

    def test_actual_completion_controls_recency_and_includes_stated_snapshot_day(self):
        result = self.calculate([record(
            date="2025-10-01", completed_at="2026-10-01T23:59:59-06:00",
        )], include_records=True)
        self.assertEqual(result["record_evidence"][0]["age_days"], 0)
        self.assertEqual(result["record_evidence"][0]["date_basis"], "completed_at")
        self.assertEqual(result["evidence"]["effective_history_weight"], 1)
        self.assertEqual(result["evidence"]["completion_date_proxy_count"], 0)

    def test_participation_date_proxy_count_applies_only_to_legacy_completions(self):
        result = self.calculate([record("legacy-completion"), record("miss", status="no_show")])
        self.assertEqual(result["evidence"]["completion_date_proxy_count"], 1)

    def test_recent_counters_require_both_age_and_similarity_thresholds(self):
        config = replace(DEFAULT_CONFIG, history=replace(DEFAULT_CONFIG.history,
                         recent_window_days=365, recent_similarity_threshold=0.6))
        historical = event("new-history-event", type="workshop", format="online")
        result = self.calculate([
            record("boundary", date="2025-10-01", status="no_show"),
            record("older", date="2025-09-30", status="no_show"),
        ], historical=historical, config=config)
        self.assertEqual(result["evidence"]["recent_similar_no_shows"], 1)
        self.assertEqual(result["evidence"]["matched_history_count"], 2)

    def test_priors_similarity_half_life_and_unknown_source_are_configurable(self):
        policy = replace(DEFAULT_CONFIG.history,
            skill_similarity_weight=1, type_similarity_weight=0, format_similarity_weight=0,
            recency_half_life_days=365, prior_weight=1, neutral_value=0.25,
            feedback_prior_weight=2, feedback_neutral_value=0.75, unknown_source_weight=0.75,
        )
        config = replace(DEFAULT_CONFIG, history=policy)
        result = self.calculate([record(date="2025-10-01", assigned_by="new-source", feedback_rating=5)], config=config)
        self.assertAlmostEqual(result["compatibility"], (0.25 + 0.375) / 1.375)
        self.assertAlmostEqual(result["feedback_signal"], (1.5 + 0.375) / 2.375)
        self.assertEqual(result["evidence"]["config_snapshot"]["unknown_source_weight"], 0.75)
        cold = self.calculate(config=config)
        self.assertEqual(cold["compatibility"], 0.25)
        self.assertEqual(cold["feedback_signal"], 0.75)

    def test_zero_source_weight_yields_no_observation_and_stays_neutral(self):
        policy = replace(DEFAULT_CONFIG.history, source_weights=(("self", 0), ("manager", 0.5), ("hr", 0.25)))
        config = replace(DEFAULT_CONFIG, history=policy)
        result = self.calculate([record(feedback_rating=5)], config=config)
        self.assertEqual(result["compatibility"], 0.5)
        self.assertEqual(result["feedback_signal"], 0.5)
        self.assertEqual(result["evidence"]["zero_weight_count"], 1)
        self.assertEqual(result["evidence"]["matched_history_count"], 0)

    def test_duplicate_record_ids_deduplicate_but_distinct_participations_remain(self):
        one = record()
        result = self.calculate([one, deepcopy(one), record("attempt-2")])
        self.assertEqual(result["evidence"]["considered_history_count"], 2)
        self.assertEqual(result["evidence"]["matched_history_count"], 2)
        self.assertAlmostEqual(result["compatibility"], 0.75)
        with self.assertRaises(RecommendationInputError) as raised:
            self.calculate([one, record(status="dropped")])
        self.assertEqual(raised.exception.code, "conflicting_record_id")

    def test_other_employee_history_is_ignored_before_validation(self):
        result = self.calculate([record(employee_id="other-person", date="invalid", status="unknown", event_id="missing")])
        self.assertEqual(result["evidence"]["considered_history_count"], 0)
        self.assertEqual(result["compatibility"], 0.5)

    def test_input_order_and_repeated_calls_do_not_change_results_or_inputs(self):
        candidate, historical = event(), event("new-history-event")
        rows = [record("z-completed", date="2025-11-01", feedback_rating=4),
                record("a-missed", status="no_show"), record("m-dropped", status="dropped", score="40")]
        before = deepcopy((candidate, historical, rows))
        result = self.calculate(rows, candidate, historical, include_records=True)
        reversed_result = calculate_history_signals(
            EMPLOYEE_ID, candidate, [historical, candidate], list(reversed(rows)),
            as_of=date(2026, 10, 1), include_records=True,
        )
        self.assertEqual(result, reversed_result)
        self.assertEqual((candidate, historical, rows), before)
        self.assertEqual([r["record_id"] for r in result["record_evidence"]], ["a-missed", "m-dropped", "z-completed"])
        result["evidence"]["config_snapshot"]["source_weights"]["self"] = 0
        self.assertEqual(self.calculate(rows, candidate, historical, include_records=True), reversed_result)
        self.assertEqual((candidate, historical, rows), before)

    def test_default_evidence_omits_record_identifiers_and_free_text(self):
        result = self.calculate([record("private-participation-id", feedback_text="private manager conversation")])
        serialized = json.dumps(result)
        self.assertNotIn("private-participation-id", serialized)
        self.assertNotIn("private manager conversation", serialized)
        self.assertNotIn("record_evidence", result)

    def test_invalid_required_dates_references_and_statuses_have_boundary_errors(self):
        cases = [
            (record(date="not-a-date"), "invalid_date"),
            (record(event_id="unknown-event"), "unknown_event"),
            (record(status="finished"), "invalid_history_status"),
            (record(completed_at="2026-09-30"), "completion_before_participation"),
            (record(status="in_progress", completed_at=SNAPSHOT), "completion_on_noncompleted_record"),
        ]
        for row, code in cases:
            with self.subTest(code=code), self.assertRaises(RecommendationInputError) as raised:
                self.calculate([row])
            self.assertEqual(raised.exception.code, code)

    def test_scores_remain_finite_and_bounded_for_many_positive_or_negative_attempts(self):
        for status, rating in (("completed", 5), ("no_show", 1)):
            with self.subTest(status=status):
                result = self.calculate([record("r-%04d" % i, status=status, feedback_rating=rating) for i in range(300)])
                self.assertGreaterEqual(result["compatibility"], 0)
                self.assertLessEqual(result["compatibility"], 1)
                self.assertGreaterEqual(result["feedback_signal"], 0)
                self.assertLessEqual(result["feedback_signal"], 1)
                json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
