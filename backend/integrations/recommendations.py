"""Validate the full engine boundary without duplicating its nested models.

The source of these JSON shapes remains recommendation/contracts.py and
ai/contracts.py. The adapter only adds the optional explanation fields.
"""
from copy import deepcopy
import json
from typing import Dict, List, Protocol, get_args, get_origin, get_type_hints

from pydantic import ConfigDict, Field, RootModel, model_validator
from typing_extensions import NotRequired, Required, TypedDict

from backend.ai.contracts import Explanation, ExplanationMetadata
from backend.data.repository import RepositoryView
from backend.models.domain import DomainModel
from backend.recommendation.contracts import (
    RankedRecommendation, RecommendationResult as EngineResult,
)


def _transport_type(annotation, cache):
    """Reuse TypedDict annotations, including on Python 3.9–3.11/Pydantic 2.

    Pydantic requires typing_extensions.TypedDict below Python 3.12; the
    standalone engine intentionally uses only the standard library. Copying
    annotations here keeps that dependency and compatibility concern local.
    """
    if isinstance(annotation, type) and hasattr(annotation, "__required_keys__"):
        if annotation not in cache:
            fields = {
                key: (Required if key in annotation.__required_keys__ else NotRequired)[
                    _transport_type(value, cache)
                ]
                for key, value in get_type_hints(annotation).items()
            }
            converted = TypedDict(annotation.__name__ + "Transport", fields)
            converted.__pydantic_config__ = ConfigDict(
                extra="forbid", strict=True, allow_inf_nan=False,
            )
            cache[annotation] = converted
        return cache[annotation]
    if get_origin(annotation) is not None and hasattr(annotation, "copy_with"):
        return annotation.copy_with(tuple(_transport_type(item, cache) for item in get_args(annotation)))
    return annotation


_types = {}
_engine_type = _transport_type(EngineResult, _types)
_recommendation_type = _transport_type(RankedRecommendation, _types)
_explanation_type = _transport_type(Explanation, _types)
_meta_type = _transport_type(ExplanationMetadata, _types)

_enriched_recommendation = TypedDict("EnrichedRecommendation", {
    **{name: Required[value] for name, value in get_type_hints(_recommendation_type).items()},
    "explanation": NotRequired[_explanation_type],
})
_enriched_recommendation.__pydantic_config__ = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

_enriched_result = TypedDict("EnrichedRecommendationResult", {
    **{name: Required[value] for name, value in get_type_hints(_engine_type).items()},
    "recommendations": Required[List[_enriched_recommendation]],
    "explanation_summary": NotRequired[_explanation_type],
    "explanation_meta": NotRequired[_meta_type],
})
_enriched_result.__pydantic_config__ = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class RecommendationResult(RootModel[_enriched_result]):
    """A transparent response: validate, never rescore or rewrite engine output."""
    model_config = ConfigDict(strict=True, allow_inf_nan=False, revalidate_instances="always")

    @model_validator(mode="wrap")
    @classmethod
    def retain_original_json(cls, value, handler):
        # Pydantic permits int values for float fields. Keep the exact original
        # JSON numbers after validation instead of converting raw evidence.
        original = deepcopy(value.root if isinstance(value, cls) else value)
        json.dumps(original, allow_nan=False)
        result = handler(value)
        result.root = original
        return result

    @model_validator(mode="after")
    def consistent_result(self):
        data = self.root
        items = data["recommendations"]
        if not 0 <= len(items) <= 3 or data["recommendation_count"] != len(items):
            raise ValueError("recommendation count disagrees with selected events")
        if data["candidate_count"] < len(items):
            raise ValueError("candidate count is smaller than selected count")
        if [item["rank"] for item in items] != list(range(1, len(items) + 1)):
            raise ValueError("recommendation ranks must be consecutive in response order")
        if (data["status"] != "ok" and items) or (data["status"] == "ok" and not items):
            raise ValueError("recommendation status disagrees with selected events")
        if any(not 0 <= item["score"] <= 1 for item in items):
            raise ValueError("recommendation score must lie between zero and one")
        if data["career_state"]["employee_id"] != data["employee_id"]:
            raise ValueError("career state belongs to another employee")
        if data["career_state"]["as_of"] != data["as_of"]:
            raise ValueError("career state belongs to another calculation date")
        for name in ("target", "career_readiness", "skill_gaps"):
            if data["career_state"][name] != data[name]:
                raise ValueError("career state disagrees with top-level " + name)
        return self


class RecommendationCoverage(DomainModel):
    evaluated_count: int = Field(strict=True, ge=0)
    without_next_step_count: int = Field(strict=True, ge=0)


class RecommendationProvider(Protocol):
    def recommend(self, employee_id: str, view: RepositoryView) -> Dict:
        """Calculate from one view's assessment baseline plus complete history.

        Never substitute projected/effective skills for employee.skills.
        Async providers and an already validated RecommendationResult also work.
        """
        ...
