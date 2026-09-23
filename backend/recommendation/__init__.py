"""Deterministic career-state building blocks, independent of the API and AI."""

from .config import DEFAULT_CONFIG, HistoryConfig, RecommendationConfig, ScoringWeights
from .contracts import RecommendationInputError

__all__ = [
    "DEFAULT_CONFIG", "HistoryConfig", "RecommendationConfig",
    "ScoringWeights", "RecommendationInputError",
]
