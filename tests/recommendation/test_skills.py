"""Behavioral tests for review-baseline reconstruction using synthetic IDs."""

import copy
from datetime import date, datetime, timezone
import unittest

from backend.recommendation.contracts import RecommendationInputError
from backend.recommendation.skills import reconstruct_effective_skills


def employee(**changes):
    value = {
        "employee_id": "employee-new",
        "skills": {"python": 1},
        "last_review_date": "2026-08-01",
    }
    value.update(changes)
    return value


def event(event_id="workshop-new", *, skill_id="python", gain=1, cap=5, **changes):
    value = {
        "event_id": event_id,
        "format": "online",
        "mandatory": False,
        "develops_skills": [{"skill_id": skill_id, "gain": gain, "max_level": cap}],
    }
    value.update(changes)
    return value


def participation(record_id="attempt-1", **changes):
    value = {
        "record_id": record_id,
        "employee_id": "employee-new",
        "event_id": "workshop-new",
        "date": "2026-09-01",
        "status": "completed",
        "completion_pct": "100",
        "score": "10",
    }
    value.update(changes)
    return value


class EffectiveSkillsTests(unittest.TestCase):
    def reconstruct(self, person=None, catalog=None, records=None, **kwargs):
        return reconstruct_effective_skills(
            employee() if person is None else person,
            [event()] if catalog is None else catalog,
            [participation()] if records is None else records,
            as_of=kwargs.pop("as_of", "2026-10-01"),
            **kwargs,
        )

    def assert_invalid(self, code, **kwargs):
        with self.assertRaises(RecommendationInputError) as caught:
            self.reconstruct(**kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_completed_gain_ignores_assessment_and_percentage(self):
        result = self.reconstruct(records=[participation(completion_pct="0", score="0")])
        self.assertEqual(result["effective_skills"], {"python": 2})
        self.assertEqual(result["applied_record_ids"], ["attempt-1"])
        self.assertEqual(result["skill_changes"][0]["date_basis"], "session_date")
        self.assertTrue(result["is_estimate"])

    def test_missing_skill_multiple_gain_and_cap(self):
        result = self.reconstruct(catalog=[event(skill_id="new-skill", gain=4, cap=3)])
        self.assertEqual(result["effective_skills"], {"new-skill": 3, "python": 1})
        self.assertEqual(result["skill_changes"][0]["gain_applied"], 3)

    def test_cap_never_reduces_existing_skill_and_zero_gain_is_valid(self):
        for cap, gain in [(3, 1), (5, 0)]:
            with self.subTest(cap=cap, gain=gain):
                result = self.reconstruct(person=employee(skills={"python": 4}), catalog=[event(cap=cap, gain=gain)])
                self.assertEqual(result["effective_skills"]["python"], 4)
                self.assertEqual(result["skill_changes"][0]["gain_applied"], 0)
                self.assertEqual(result["applied_record_ids"], ["attempt-1"])

    def test_mandatory_onboarding_gains_apply_but_no_skill_events_do_not(self):
        result = self.reconstruct(catalog=[event(mandatory=True)])
        self.assertEqual(result["effective_skills"]["python"], 2)
        no_skills = self.reconstruct(catalog=[event(mandatory=True, develops_skills=[])])
        self.assertEqual(no_skills["effective_skills"]["python"], 1)
        self.assertEqual(no_skills["applied_record_ids"], [])
        self.assertFalse(no_skills["is_estimate"])

    def test_distinct_participations_apply_without_employee_event_deduplication(self):
        records = [participation("club-1", event_id="EV_036"), participation("club-2", event_id="EV_036", date="2026-09-02")]
        result = self.reconstruct(catalog=[event("EV_036")], records=records)
        self.assertEqual(result["effective_skills"]["python"], 3)
        self.assertEqual(result["applied_record_ids"], ["club-1", "club-2"])

    def test_identical_record_id_is_deduplicated_and_conflicts_rejected(self):
        record = participation()
        result = self.reconstruct(records=[record, copy.deepcopy(record)])
        self.assertEqual(result["effective_skills"]["python"], 2)
        self.assert_invalid("conflicting_record_id", records=[record, participation(date="2026-09-02")])

    def test_repeated_calls_are_idempotent_inputs_unchanged_and_order_invariant(self):
        person = employee()
        catalog = [event("low-cap", cap=2), event("high-gain", gain=2)]
        records = [participation("later", event_id="high-gain", date="2026-09-02"), participation("earlier", event_id="low-cap")]
        before = copy.deepcopy((person, catalog, records))
        first = self.reconstruct(person, catalog, records)
        second = self.reconstruct(person, list(reversed(catalog)), list(reversed(records)))
        self.assertEqual(first, second)
        self.assertEqual(first["effective_skills"]["python"], 4)
        self.assertEqual((person, catalog, records), before)

    def test_review_and_snapshot_boundaries(self):
        dates = ["2026-07-31", "2026-08-01", "2026-08-02", "2026-10-01", "2026-10-02"]
        records = [participation("r" + str(index), date=value) for index, value in enumerate(dates)]
        result = self.reconstruct(records=records, as_of=date(2026, 10, 1))
        self.assertEqual(result["effective_skills"]["python"], 3)
        self.assertEqual(result["applied_record_ids"], ["r2", "r3"])

    def test_pre_review_self_paced_enrollment_is_ambiguous_and_not_replayed(self):
        records = [participation("before", date="2026-07-01"), participation("same", date="2026-08-01"), participation("after", date="2026-09-01")]
        result = self.reconstruct(catalog=[event(format="self_paced")], records=records)
        self.assertEqual(result["effective_skills"]["python"], 2)
        self.assertEqual(result["uncertain_record_ids"], ["before", "same"])
        self.assertEqual(result["skill_changes"][0]["date_basis"], "enrollment_date")
        self.assertEqual({warning["code"] for warning in result["warnings"]}, {"ambiguous_self_paced_completion", "completion_date_proxy"})

    def test_actual_completion_overrides_old_enrollment_date(self):
        values = ["2026-09-10", "2026-09-10T23:59:59Z", date(2026, 9, 10), datetime(2026, 9, 10, 23, tzinfo=timezone.utc)]
        for value in values:
            with self.subTest(completed_at=value):
                result = self.reconstruct(catalog=[event(format="self_paced")], records=[participation(date="2026-07-01", completed_at=value)])
                self.assertEqual(result["effective_skills"]["python"], 2)
                self.assertEqual(result["skill_changes"][0]["date_basis"], "completed_at")
                self.assertEqual(result["uncertain_record_ids"], [])
                self.assertFalse(result["is_estimate"])

    def test_snapshot_uses_stated_date_and_includes_whole_day(self):
        result = self.reconstruct(records=[participation(completed_at="2026-10-01T23:59:59-06:00")])
        self.assertEqual(result["effective_skills"]["python"], 2)
        future = self.reconstruct(records=[participation(completed_at="2026-10-02T00:00:00+06:00")])
        self.assertEqual(future["effective_skills"]["python"], 1)

    def test_exact_timestamps_order_by_instant_not_id_or_lexical_time(self):
        catalog = [event("low-cap", cap=2), event("high-gain", gain=2)]
        records = [
            participation("z-earlier", event_id="low-cap", completed_at="2026-09-01T12:00:00+05:00"),
            participation("a-later", event_id="high-gain", completed_at="2026-09-01T08:00:00Z"),
        ]
        result = self.reconstruct(catalog=catalog, records=records)
        self.assertEqual(result["effective_skills"]["python"], 4)
        self.assertEqual(result["applied_record_ids"], ["z-earlier", "a-later"])
        self.assertFalse(result["is_estimate"])

    def test_date_only_same_day_overlapping_gains_disclose_unknown_order(self):
        records = [participation("a", completed_at="2026-09-01"), participation("b", completed_at="2026-09-01T12:00:00Z")]
        result = self.reconstruct(records=records)
        self.assertTrue(result["is_estimate"])
        self.assertEqual(result["warnings"][0]["code"], "ambiguous_completion_order")
        self.assertEqual(result, self.reconstruct(records=list(reversed(records))))

    def test_offset_timestamps_and_date_only_values_use_utc_uncertainty_intervals(self):
        catalog = [event("low-cap", cap=2), event("high-gain", gain=2)]
        for date_only_or_exact in ["2026-09-02", "2026-09-02T00:30:00Z"]:
            with self.subTest(completed_at=date_only_or_exact):
                records = [
                    participation("a", event_id="low-cap", completed_at=date_only_or_exact),
                    participation("b", event_id="high-gain", completed_at="2026-09-01T23:30:00-01:00"),
                ]
                result = self.reconstruct(catalog=catalog, records=records)
                self.assertEqual(result["effective_skills"]["python"], 4)
                self.assertTrue(result["is_estimate"])
                self.assertEqual(result["warnings"][0]["code"], "ambiguous_completion_order")
                self.assertEqual(result["warnings"][0]["record_ids"], ["a", "b"])
                self.assertEqual(result, self.reconstruct(catalog=catalog, records=list(reversed(records))))

    def test_nonoverlapping_completion_days_do_not_create_order_warning(self):
        records = [
            participation("a", completed_at="2026-09-01"),
            participation("b", completed_at="2026-09-02T00:00:00Z"),
        ]
        result = self.reconstruct(records=records)
        self.assertEqual(result["warnings"], [])
        self.assertFalse(result["is_estimate"])

    def test_rejects_nonsequence_catalog_and_history_with_engine_errors(self):
        for invalid in [None, 1, "records", b"records", {"events": []}, {"history": []}]:
            with self.subTest(value=invalid):
                with self.assertRaises(RecommendationInputError) as caught:
                    reconstruct_effective_skills(employee(), invalid, [], as_of="2026-10-01")
                self.assertEqual(caught.exception.code, "invalid_events")
                with self.assertRaises(RecommendationInputError) as caught:
                    reconstruct_effective_skills(employee(), [], invalid, as_of="2026-10-01")
                self.assertEqual(caught.exception.code, "invalid_history")

    def test_noncompleted_statuses_never_grant_gains(self):
        for status in ["no_show", "dropped", "declined", "overdue", "in_progress"]:
            with self.subTest(status=status):
                result = self.reconstruct(records=[participation(status=status, completion_pct="100", score="100")])
                self.assertEqual(result["effective_skills"]["python"], 1)

    def test_other_employee_rows_are_ignored_before_validation(self):
        result = self.reconstruct(records=[participation(employee_id="someone-else", event_id="unknown", date="bad", status="unknown")])
        self.assertEqual(result["effective_skills"]["python"], 1)

    def test_invalid_dates_and_chronology_raise_actionable_errors(self):
        cases = [
            ("invalid_date", {"records": [participation(date="2026-02-30")]}),
            ("invalid_date", {"records": [participation(completed_at="nonsense")]}),
            ("review_after_snapshot", {"person": employee(last_review_date="2026-10-02")}),
            ("completion_before_participation", {"records": [participation(completed_at="2026-08-31")]}),
            ("completion_before_participation", {"records": [participation(date="2026-09-01T12:00:00Z", completed_at="2026-09-01T11:59:59Z")]}),
            ("completion_on_noncompleted_record", {"records": [participation(status="in_progress", completed_at="2026-09-01")]}),
        ]
        for code, kwargs in cases:
            with self.subTest(code=code, kwargs=kwargs):
                self.assert_invalid(code, **kwargs)

    def test_invalid_references_and_catalog_ambiguities_raise_errors(self):
        self.assert_invalid("unknown_event", records=[participation(event_id="unknown")])
        self.assert_invalid("duplicate_event_id", catalog=[event(), event()])
        self.assert_invalid("duplicate_developed_skill", catalog=[event(develops_skills=[{"skill_id": "python", "gain": 1, "max_level": 5}] * 2)])
        self.assert_invalid("invalid_history_status", records=[participation(status="finished")])

    def test_invalid_skill_arithmetic_values_raise_errors(self):
        for value in [-1, 6, True, 1.5, "2"]:
            with self.subTest(level=value):
                self.assert_invalid("invalid_skill_level", person=employee(skills={"python": value}))
                self.assert_invalid("invalid_skill_level", catalog=[event(cap=value)])
        for value in [-1, True, 1.5, "2"]:
            with self.subTest(gain=value):
                self.assert_invalid("invalid_gain", catalog=[event(gain=value)])


if __name__ == "__main__":
    unittest.main()
