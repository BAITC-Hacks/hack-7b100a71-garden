"""JSON-friendly engine boundary, not backend persistence or Pydantic models.

Bekarys's backend adapts validated data to these small mapping inputs. Extra
application fields are ignored. Importing these contracts needs only Python.
"""

from datetime import date, datetime
from typing import Dict, List, Literal, Mapping, Optional, Sequence, TypedDict, Union


CalendarDate = Union[str, date]
DateValue = Union[str, date, datetime]


class RecommendationInputError(ValueError):
    """Boundary error with a stable code; HTTP translation belongs to the API."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CareerGoalInput(TypedDict):
    target_role: str
    target_grade: str


class EmployeeInput(TypedDict):
    employee_id: str
    role: str
    grade: str
    career_goal: Optional[CareerGoalInput]
    skills: Mapping[str, int]
    last_review_date: CalendarDate


class RoleProfileInput(TypedDict):
    role: str
    grade: str
    required_skills: Mapping[str, int]
    critical_skills: Sequence[str]


class SkillDevelopmentInput(TypedDict):
    skill_id: str
    gain: int
    max_level: int


class EventInput(TypedDict):
    event_id: str
    format: str
    develops_skills: Sequence[SkillDevelopmentInput]


class _ParticipationRequired(TypedDict):
    record_id: str
    employee_id: str
    event_id: str
    date: DateValue
    status: str


class ParticipationInput(_ParticipationRequired, total=False):
    completed_at: Optional[DateValue]


class CareerTarget(TypedDict):
    role: str
    grade: str
    source: Literal["career_goal", "next_grade"]


class TargetResolution(TypedDict):
    status: Literal["resolved", "no_next_grade"]
    target: Optional[CareerTarget]


class SkillGap(TypedDict):
    skill_id: str
    current: int
    required: int
    gap: int
    critical: bool


class ReadinessResult(TypedDict):
    current: Optional[float]
    status: Literal["available", "unavailable"]
    reason: Optional[str]
    critical_weight: float
    weighted_covered_levels: float
    weighted_required_levels: float
    critical_requirements_met: Optional[bool]
    remaining_critical_gaps: List[SkillGap]
    all_requirements_met: Optional[bool]


class ReconstructionWarning(TypedDict):
    code: str
    message: str
    record_ids: List[str]


class SkillChange(TypedDict):
    record_id: str
    event_id: str
    skill_id: str
    before: int
    after: int
    gain_applied: int
    date_basis: str


class SkillsReconstruction(TypedDict):
    effective_skills: Dict[str, int]
    applied_record_ids: List[str]
    skill_changes: List[SkillChange]
    uncertain_record_ids: List[str]
    warnings: List[ReconstructionWarning]
    date_policy: str
    is_estimate: bool


class CareerState(TypedDict):
    employee_id: str
    as_of: str
    status: Literal["ok", "target_satisfied", "no_next_grade", "invalid_target_requirements"]
    target: Optional[CareerTarget]
    skill_gaps: List[SkillGap]
    career_readiness: Optional[ReadinessResult]
    skills_reconstruction: SkillsReconstruction
