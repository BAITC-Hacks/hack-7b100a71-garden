"""The approved policy can be inspected and tuned from one configuration."""

from dataclasses import FrozenInstanceError, replace
import unittest

from backend.recommendation.config import DEFAULT_CONFIG, HistoryConfig, RecommendationConfig, ScoringWeights
from backend.recommendation.contracts import RecommendationInputError


class ConfigurationTests(unittest.TestCase):
    def test_default_configuration_exposes_approved_career_policy(self):
        self.assertIsInstance(DEFAULT_CONFIG, RecommendationConfig)
        self.assertEqual(DEFAULT_CONFIG.readiness_critical_weight, 2)
        self.assertEqual(DEFAULT_CONFIG.skill_min_level, 0)
        self.assertEqual(DEFAULT_CONFIG.skill_max_level, 5)
        self.assertEqual(DEFAULT_CONFIG.grades, ("Junior", "Middle", "Senior", "Lead"))

    def test_all_seven_scoring_weights_match_approved_model_and_sum_to_one(self):
        weights = DEFAULT_CONFIG.scoring_weights
        self.assertIsInstance(weights, ScoringWeights)
        expected = {
            "critical_skill_impact": 0.35,
            "gap_reduction": 0.25,
            "career_relevance": 0.15,
            "historical_compatibility": 0.10,
            "history_feedback_signal": 0.05,
            "effort_efficiency": 0.05,
            "availability": 0.05,
        }
        self.assertEqual({name: getattr(weights, name) for name in expected}, expected)
        self.assertAlmostEqual(sum(getattr(weights, name) for name in expected), 1)

    def test_defaults_are_frozen_and_tuning_does_not_change_them(self):
        with self.assertRaises(FrozenInstanceError):
            DEFAULT_CONFIG.readiness_critical_weight = 3
        with self.assertRaises(FrozenInstanceError):
            DEFAULT_CONFIG.scoring_weights.gap_reduction = 0.1
        alternative = replace(DEFAULT_CONFIG, readiness_critical_weight=3)
        self.assertEqual(alternative.readiness_critical_weight, 3)
        self.assertEqual(DEFAULT_CONFIG.readiness_critical_weight, 2)

    def test_input_errors_are_value_errors_with_machine_readable_code(self):
        error = RecommendationInputError("invalid_test_input", "A useful explanation")
        self.assertIsInstance(error, ValueError)
        self.assertEqual(error.code, "invalid_test_input")
        self.assertIn("A useful explanation", str(error))

    def test_nested_configuration_cannot_be_replaced_by_mutable_dictionaries(self):
        for overrides in ({"history": {}}, {"scoring_weights": {}}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    RecommendationConfig(**overrides)

    def test_scoring_weights_reject_nonunit_total_nonfinite_and_negative_values(self):
        for overrides in ({"availability": 0.1}, {"availability": float("nan")},
                          {"availability": -0.1}, {"availability": True}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                ScoringWeights(**overrides)

    def test_history_priors_fallback_and_diagnostic_thresholds_are_centralized(self):
        config = DEFAULT_CONFIG.history
        self.assertEqual((config.prior_weight, config.neutral_value), (2, 0.5))
        self.assertEqual((config.feedback_prior_weight, config.feedback_neutral_value), (2, 0.5))
        self.assertEqual(config.unknown_source_weight, 0.5)
        self.assertEqual(config.recent_window_days, 365)
        self.assertEqual(config.recent_similarity_threshold, 0.5)
        self.assertEqual(DEFAULT_CONFIG.availability_wait_scale_days, 30)

    def test_history_tuning_rejects_invalid_priors_and_counter_thresholds(self):
        for overrides in ({"feedback_prior_weight": 0}, {"feedback_neutral_value": 2},
                          {"unknown_source_weight": -1}, {"recent_window_days": -1},
                          {"recent_window_days": True}, {"recent_similarity_threshold": 2}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                HistoryConfig(**overrides)


if __name__ == "__main__":
    unittest.main()
