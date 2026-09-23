"""Typed boundary for Zhanibek's engine. No scoring or target-selection logic."""
from typing import Any, Dict, List, Optional, Protocol

from pydantic import Field

from backend.data.repository import RepositoryView
from backend.models.domain import DomainModel, Grade, NonEmptyString, SkillLevel


class CareerTarget(DomainModel):
    role: NonEmptyString
    grade: Grade


class RecommendationEvidence(DomainModel):
    factor: NonEmptyString
    explanation: NonEmptyString
    values: Dict[str, Any] = Field(default_factory=dict)


class ProjectedSkillChange(DomainModel):
    skill_id: NonEmptyString
    before: SkillLevel
    after: SkillLevel


class Recommendation(DomainModel):
    event_id: NonEmptyString
    reason: NonEmptyString
    evidence: List[RecommendationEvidence] = Field(min_length=2)
    skill_changes: List[ProjectedSkillChange] = Field(default_factory=list)


class RecommendationResult(DomainModel):
    employee_id: NonEmptyString
    target: Optional[CareerTarget] = None
    career_readiness: Optional[float] = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    recommendations: List[Recommendation] = Field(max_length=3)
    notes: List[str] = Field(default_factory=list)


class RecommendationCoverage(DomainModel):
    evaluated_count: int = Field(strict=True, ge=0)
    without_next_step_count: int = Field(strict=True, ge=0)


class RecommendationProvider(Protocol):
    def recommend(self, employee_id: str, view: RepositoryView) -> RecommendationResult:
        """Return a typed result (or its dict); async implementations also work.

        Use view.get_effective_skills rather than replaying history again.
        Own target selection, scoring, evidence, readiness, and AI explanations.
        """
        ...
