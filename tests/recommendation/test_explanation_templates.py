"""Localized facts preserve evidence, units and uncertainty in both variants."""

from collections import Counter
from copy import deepcopy
import re
import unittest

from backend.ai.templates import CODES, LANGUAGES, REJECTION_CODES, VARIANTS, render_fact


FACTS = {
    "target": {"role": "Unseen Research Role", "grade": "Senior"},
    "impact": {"total": 5, "critical": 3},
    "skill": {"skill_id": "JURY_SKILL_NEW", "before": 1, "after": 3, "required": 4,
              "gap_before": 3, "gap_after": 1, "critical": True},
    "readiness": {"before": 0.4251, "after": 0.5678, "delta": 0.1427},
    "closures": {"total": 3, "critical": 2},
    "audience_current": {"current_role": "Current Role", "attained_grade": "Middle"},
    "audience_target": {"current_role": "Current Role", "target_role": "Destination Role", "attained_grade": "Middle"},
    "audience_both": {"current_role": "Current Role", "target_role": "Destination Role", "attained_grade": "Middle"},
    "availability_self_paced": {},
    "availability_scheduled": {"date": "2026-10-19", "days": 18},
    "usefulness": {"useful": 2, "actual": 5},
    "history_cold": {"compatibility": 0.5},
    "history_observed": {"count": 11, "compatibility": 0.43212, "no_shows": 2,
                         "completions": 5, "recent_days": 180, "similarity_min": 0.625},
    "feedback": {"ratings": 7, "assessments": 9, "signal": 0.71256},
    "estimate": {},
    "readiness_note": {},
    "status_ok": {"count": 2, "candidates": 7},
    "status_no_eligible_recommendations": {},
    "status_no_next_grade": {},
    "status_target_satisfied": {},
    "status_invalid_target_requirements": {},
    "blocked_reason": {"reason_code": "PREREQUISITE_NOT_MET", "count": 6},
    "uncovered_gap": {"skill_id": "JURY_SKILL_NEW", "current": 1, "required": 4, "gap": 3},
}


def numbers(text):
    return Counter(re.findall(r"(?<!\w)[+-]?\d+(?:\.\d+)?", text))


class ExplanationTemplateTests(unittest.TestCase):
    def test_all_fact_codes_have_nonempty_distinct_variants_in_all_languages(self):
        self.assertEqual(set(CODES), set(FACTS))
        self.assertEqual(LANGUAGES, ("kk", "ru", "en"))
        self.assertEqual(VARIANTS, ("direct", "coaching"))
        for language in LANGUAGES:
            for code, values in FACTS.items():
                with self.subTest(language=language, code=code):
                    direct = render_fact(code, values, language)
                    coaching = render_fact(code, values, language, "coaching")
                    self.assertTrue(direct.strip())
                    self.assertTrue(coaching.strip())
                    self.assertNotEqual(direct, coaching)
                    self.assertNotRegex(direct + coaching, r"\{[a-z_]+\}")
                    self.assertEqual(numbers(direct), numbers(coaching))

    def test_catalog_identifiers_roles_and_grades_are_preserved_verbatim(self):
        identifier_fields = ("role", "grade", "skill_id", "current_role", "target_role", "attained_grade", "date")
        for language in LANGUAGES:
            for variant in VARIANTS:
                for code, values in FACTS.items():
                    with self.subTest(language=language, variant=variant, code=code):
                        text = render_fact(code, values, language, variant)
                        for field in identifier_fields:
                            if field in values:
                                self.assertIn(values[field], text)

    def test_readiness_uses_percentages_and_percentage_points_not_fraction_or_relative_growth(self):
        unit = {"en": "percentage points", "ru": "процентного пункта", "kk": "пайыздық тармақ"}
        for language in LANGUAGES:
            for variant in VARIANTS:
                with self.subTest(language=language, variant=variant):
                    text = render_fact("readiness", FACTS["readiness"], language, variant)
                    self.assertIn("42.51%", text)
                    self.assertIn("56.78%", text)
                    self.assertIn("+14.27", text)
                    self.assertIn(unit[language], text)
                    self.assertNotIn("0.1427", text)
                    self.assertEqual(text.count("%"), 2)
                    unchanged = render_fact("readiness", {"before": 1.0, "after": 1.0, "delta": 0.0}, language, variant)
                    self.assertIn("100.00%", unchanged)
                    self.assertIn("+0.00", unchanged)

    def test_history_keeps_exact_configured_window_threshold_and_distinct_counts(self):
        for language in LANGUAGES:
            for variant in VARIANTS:
                with self.subTest(language=language, variant=variant):
                    text = render_fact("history_observed", FACTS["history_observed"], language, variant)
                    self.assertEqual(numbers(text), Counter({"11": 1, "0.432": 1, "180": 1, "0.625": 1, "2": 1, "5": 1}))
                    self.assertIn("≥ 0.625", text)
                    self.assertNotIn("365", text)

    def test_history_and_feedback_signals_use_three_decimal_places(self):
        for language in LANGUAGES:
            for variant in VARIANTS:
                with self.subTest(language=language, variant=variant):
                    cold = render_fact("history_cold", FACTS["history_cold"], language, variant)
                    self.assertIn("0.500", cold)
                    feedback = render_fact("feedback", FACTS["feedback"], language, variant)
                    self.assertEqual(numbers(feedback), Counter({"7": 1, "9": 1, "0.713": 1}))

    def test_critical_false_is_not_rendered_as_critical_true(self):
        critical_words = {
            "en": ("critical for the target", "noncritical for the target"),
            "ru": ("критический навык для цели", "некритический навык для цели"),
            "kk": ("мақсат үшін критикалық дағды", "мақсат үшін критикалық емес дағды"),
        }
        for language, (positive, negative) in critical_words.items():
            for variant in VARIANTS:
                with self.subTest(language=language, variant=variant):
                    first = render_fact("skill", FACTS["skill"], language, variant)
                    second = render_fact("skill", dict(FACTS["skill"], critical=False), language, variant)
                    self.assertIn(positive, first)
                    self.assertIn(negative, second)
                    self.assertNotEqual(first, second)
                    self.assertEqual(numbers(first), numbers(second))

    def test_simulated_effects_are_marked_as_model_results_in_every_language(self):
        model_words = {"en": ("simulat", "model"), "ru": ("симуляц", "модел"), "kk": ("симуляц", "модель")}
        for language in LANGUAGES:
            for variant in VARIANTS:
                for code in ("impact", "skill", "readiness", "closures", "usefulness"):
                    with self.subTest(language=language, variant=variant, code=code):
                        text = render_fact(code, FACTS[code], language, variant).lower()
                        self.assertTrue(any(word in text for word in model_words[language]), text)

    def test_transition_audience_preserves_current_grade_and_application_policy(self):
        policy_words = {"en": "policy", "ru": "политик", "kk": "саясат"}
        for language in LANGUAGES:
            for variant in VARIANTS:
                for code in ("audience_target", "audience_both"):
                    with self.subTest(language=language, variant=variant, code=code):
                        text = render_fact(code, FACTS[code], language, variant)
                        self.assertIn("Current Role", text)
                        self.assertIn("Destination Role", text)
                        self.assertIn("Middle", text)
                        self.assertIn(policy_words[language], text)
                        self.assertNotIn("Senior", text)

    def test_all_rejection_codes_have_distinct_localized_reasons_and_exact_counts(self):
        prerequisite_phrase = {"en": "prerequisite", "ru": "предварительное требование", "kk": "алдын ала талап"}
        for language in LANGUAGES:
            for variant in VARIANTS:
                with self.subTest(language=language, variant=variant):
                    rendered = [render_fact("blocked_reason", {"reason_code": code, "count": 17}, language, variant)
                                for code in REJECTION_CODES]
                    self.assertEqual(len(set(rendered)), 9)
                    for text in rendered:
                        self.assertEqual(numbers(text), Counter({"17": 1}))
                        self.assertNotIn("PREREQUISITE_NOT_MET", text)
                    prerequisite = render_fact("blocked_reason", {"reason_code": "PREREQUISITE_NOT_MET", "count": 17}, language, variant)
                    self.assertIn(prerequisite_phrase[language], prerequisite)

    def test_uncovered_gap_describes_current_catalog_potential_not_full_future_trajectory(self):
        admission_phrase = {"en": "ignoring admission", "ru": "без учёта условий допуска", "kk": "қатысу шарттарын"}
        for language in LANGUAGES:
            for variant in VARIANTS:
                with self.subTest(language=language, variant=variant):
                    text = render_fact("uncovered_gap", FACTS["uncovered_gap"], language, variant)
                    self.assertIn("JURY_SKILL_NEW", text)
                    self.assertEqual(numbers(text), Counter({"1": 1, "4": 1, "3": 1}))
                    self.assertIn(admission_phrase[language], text.lower())

    def test_readiness_note_and_estimate_preserve_limitations(self):
        no_guarantee = {"en": ("does not guarantee", "without a promotion guarantee"),
                        "ru": ("не гарантирует", "без гарантии"),
                        "kk": ("кепілдік бермейді", "кепілдік емес")}
        uncertainty = {"en": ("estimate", "uncertain"), "ru": ("приблиз", "неопределён", "однозначно"),
                       "kk": ("шамамен", "белгісіздік", "бірмәнді")}
        for language in LANGUAGES:
            for variant in VARIANTS:
                with self.subTest(language=language, variant=variant):
                    note = render_fact("readiness_note", {}, language, variant)
                    self.assertTrue(any(phrase in note for phrase in no_guarantee[language]), note)
                    estimate = render_fact("estimate", {}, language, variant)
                    self.assertTrue(any(phrase in estimate for phrase in uncertainty[language]), estimate)

    def test_kazakh_text_is_localized_and_uses_expected_domain_terms(self):
        checks = {
            "target": "Мақсат", "readiness": "мақсат талаптарының",
            "history_observed": "үйлесімділік", "feedback": "Кері байланыстың",
            "availability_scheduled": "қолжетімді", "status_no_next_grade": "мансаптық мақсат",
        }
        for code, phrase in checks.items():
            with self.subTest(code=code):
                text = render_fact(code, FACTS[code], "kk")
                self.assertIn(phrase, text)
                self.assertTrue(any(letter in text for letter in "әғқңөұүһі"), text)

    def test_unsupported_choices_fail_without_silent_fallback(self):
        for language in ("kz", "de", "", None, []):
            with self.subTest(language=language), self.assertRaises(ValueError):
                render_fact("target", FACTS["target"], language)
        for variant in ("creative", "", None, []):
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                render_fact("target", FACTS["target"], "ru", variant)
        for code in ("invent_reason", "", None, []):
            with self.subTest(code=code), self.assertRaises(ValueError):
                render_fact(code, {}, "en")
        with self.assertRaises(ValueError):
            render_fact("blocked_reason", {"reason_code": "UNKNOWN", "count": 1}, "en")
        with self.assertRaises(ValueError):
            render_fact("target", None, "en")

    def test_boolean_critical_flag_is_required(self):
        for invalid in ("false", 0, 1, None):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                render_fact("skill", dict(FACTS["skill"], critical=invalid), "kk")

    def test_values_are_not_mutated_and_catalog_text_is_never_reinterpreted(self):
        before = deepcopy(FACTS)
        for language in LANGUAGES:
            for variant in VARIANTS:
                for code, values in FACTS.items():
                    first = render_fact(code, values, language, variant)
                    self.assertEqual(first, render_fact(code, values, language, variant))
        self.assertEqual(FACTS, before)
        unusual_role = "User's {literal_role} / Новая роль"
        text = render_fact("target", {"role": unusual_role, "grade": "G-α"}, "kk")
        self.assertIn(unusual_role, text)
        self.assertIn("G-α", text)

    def test_derived_display_values_cannot_override_validated_evidence(self):
        readiness = dict(FACTS["readiness"], before_pct="100", after_pct="100", delta_pp="99")
        text = render_fact("readiness", readiness, "en")
        self.assertIn("42.51%", text)
        self.assertIn("56.78%", text)
        self.assertIn("+14.27", text)
        observed = dict(FACTS["history_observed"], compatibility_fmt="1.000", similarity_fmt="0.001")
        text = render_fact("history_observed", observed, "ru")
        self.assertIn("0.432", text)
        self.assertIn("0.625", text)
        text = render_fact("blocked_reason", dict(FACTS["blocked_reason"], reason_label="invented"), "kk")
        self.assertNotIn("invented", text)


if __name__ == "__main__":
    unittest.main()
