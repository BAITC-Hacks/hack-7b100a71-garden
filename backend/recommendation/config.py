"""Central policy settings. Scoring/history settings are reserved for Step 2."""

from dataclasses import dataclass, field
from math import isfinite
from typing import Tuple


def _positive(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value <= 0:
        raise ValueError("{} must be a positive finite number".format(name))


def _unit(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not 0 <= value <= 1:
        raise ValueError("{} must be between zero and one".format(name))


@dataclass(frozen=True)
class ScoringWeights:
    critical_skill_impact: float = 0.35
    gap_reduction: float = 0.25
    career_relevance: float = 0.15
    historical_compatibility: float = 0.10
    history_feedback_signal: float = 0.05
    effort_efficiency: float = 0.05
    availability: float = 0.05

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            _unit(value, name)
        if abs(sum(vars(self).values()) - 1.0) > 1e-12:
            raise ValueError("Scoring weights must sum to one")


@dataclass(frozen=True)
class HistoryConfig:
    skill_similarity_weight: float = 0.60
    type_similarity_weight: float = 0.25
    format_similarity_weight: float = 0.15
    recency_half_life_days: float = 365.0
    prior_weight: float = 2.0
    neutral_value: float = 0.5
    source_weights: Tuple[Tuple[str, float], ...] = (
        ("self", 1.0), ("manager", 0.5), ("hr", 0.25),
    )
    status_outcomes: Tuple[Tuple[str, float], ...] = (
        ("completed", 1.0), ("dropped", 0.25),
        ("no_show", 0.0), ("declined", 0.40),
    )
    excluded_statuses: Tuple[str, ...] = ("in_progress", "overdue")
    include_mandatory: bool = False

    def __post_init__(self) -> None:
        values = (self.skill_similarity_weight, self.type_similarity_weight, self.format_similarity_weight)
        for value in values:
            _unit(value, "similarity weight")
        if abs(sum(values) - 1.0) > 1e-12:
            raise ValueError("History similarity weights must sum to one")
        _positive(self.recency_half_life_days, "recency_half_life_days")
        _positive(self.prior_weight, "prior_weight")
        _unit(self.neutral_value, "neutral_value")
        for name, pairs in (("source_weights", self.source_weights), ("status_outcomes", self.status_outcomes)):
            if not isinstance(pairs, tuple) or any(not isinstance(pair, tuple) or len(pair) != 2 for pair in pairs):
                raise ValueError("{} must be immutable (name, weight) pairs".format(name))
            if len({key for key, _ in pairs}) != len(pairs):
                raise ValueError("{} contains duplicate keys".format(name))
            for key, value in pairs:
                if not isinstance(key, str) or not key:
                    raise ValueError("{} keys must be nonempty strings".format(name))
                _unit(value, name)
        if not isinstance(self.excluded_statuses, tuple) or set(self.excluded_statuses) & dict(self.status_outcomes).keys():
            raise ValueError("Excluded statuses must be immutable and have no outcome value")


@dataclass(frozen=True)
class RecommendationConfig:
    grades: Tuple[str, ...] = ("Junior", "Middle", "Senior", "Lead")
    skill_min_level: int = 0
    skill_max_level: int = 5
    readiness_critical_weight: float = 2.0
    recurring_event_ids: Tuple[str, ...] = ("EV_036",)
    availability_wait_scale_days: float = 30.0
    scoring_weights: ScoringWeights = field(default_factory=ScoringWeights)
    history: HistoryConfig = field(default_factory=HistoryConfig)
    history_statuses: Tuple[str, ...] = (
        "completed", "in_progress", "dropped", "no_show", "declined", "overdue",
    )
    event_formats: Tuple[str, ...] = ("online", "offline", "self_paced")

    def __post_init__(self) -> None:
        if not isinstance(self.scoring_weights, ScoringWeights) or not isinstance(self.history, HistoryConfig):
            raise ValueError("scoring_weights and history must be immutable configuration objects")
        if not isinstance(self.grades, tuple) or not self.grades or len(set(self.grades)) != len(self.grades):
            raise ValueError("grades must be a nonempty tuple of unique names in ascending order")
        if any(not isinstance(grade, str) or not grade for grade in self.grades):
            raise ValueError("Grade names must be nonempty strings")
        if type(self.skill_min_level) is not int or self.skill_min_level != 0:
            raise ValueError("skill_min_level must be zero: absent skills mean zero")
        if type(self.skill_max_level) is not int or self.skill_max_level <= self.skill_min_level:
            raise ValueError("skill_max_level must be an integer above skill_min_level")
        _positive(self.readiness_critical_weight, "readiness_critical_weight")
        _positive(self.availability_wait_scale_days, "availability_wait_scale_days")
        for name in ("recurring_event_ids", "history_statuses", "event_formats"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or any(not isinstance(value, str) or not value for value in values) or len(set(values)) != len(values):
                raise ValueError("{} must be an immutable tuple of unique strings".format(name))


DEFAULT_CONFIG = RecommendationConfig()
