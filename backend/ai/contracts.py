"""Explanation-boundary dictionaries; no backend application or HTTP models."""

from typing import Dict, List, Literal, TypedDict


class ExplanationFact(TypedDict):
    fact_id: str
    code: str
    values: Dict[str, object]
    evidence_paths: List[str]


class ExplanationSegment(TypedDict):
    fact_id: str
    text: str


class Explanation(TypedDict):
    language: Literal["kk", "ru", "en"]
    source: Literal["deterministic", "openai"]
    text: str
    facts: List[ExplanationFact]
    segments: List[ExplanationSegment]


class ExplanationMetadata(TypedDict):
    requested_language: object
    language: str
    language_fallback: bool
    openai_requested: bool
    provider_status: str
