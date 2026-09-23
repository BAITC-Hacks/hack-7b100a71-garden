"""The approved policy can be inspected and tuned from one configuration."""

from dataclasses import FrozenInstanceError, replace
import unittest

from backend.recommendation.config import DEFAULT_CONFIG, RecommendationConfig, ScoringWeights
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


if __name__ == "__main__":
    unittest.main()
