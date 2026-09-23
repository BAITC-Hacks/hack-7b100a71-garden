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
    # Trusted runtime adapter context, never inferred for imported history.
    # completed_at retains the real operation timestamp; completed_on is the
    # explicit business date in the dataset snapshot's logical clock.
    completed_on: Optional[CalendarDate]
    runtime_sequence: Optional[int]


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


# Step 2 adds boundary contracts without changing the Step 1 inputs or results.
class _EligibilityEventRequired(EventInput):
    mandatory: bool
    target_roles: Sequence[str]
    target_grades: Sequence[str]
    prerequisites: Mapping[str, int]
    upcoming_sessions: Sequence[CalendarDate]


class EligibilityEventInput(_EligibilityEventRequired, total=False):
    title: str


class TargetProfileRef(TypedDict):
    role: str
    grade: str


RejectionCode = Literal[
    "MANDATORY", "ROLE_MISMATCH", "GRADE_MISMATCH", "PREREQUISITE_NOT_MET",
    "ALREADY_COMPLETED", "ALREADY_IN_PROGRESS", "NO_TARGET_GAP_IMPACT",
    "NO_UPCOMING_SESSION", "NO_CAREER_TARGET",
]


class RejectionReason(TypedDict):
    code: RejectionCode
    message: str


class PrerequisiteCheck(TypedDict):
    skill_id: str
    current: int
    required: int
    met: bool


class SkillImpact(TypedDict):
    skill_id: str
    before: int
    advertised_gain: int
    max_level: int
    after: int
    actual_gain: int


class TargetSkillImpact(TypedDict):
    skill_id: str
    current: int
    required: int
    gap_before: int
    after: int
    gap_after: int
    useful_gain: int
    critical: bool


class EventSimulation(TypedDict):
    event_id: str
    target: TargetProfileRef
    simulated_skills_after: Dict[str, int]
    skill_impact: List[SkillImpact]
    target_skill_impact: List[TargetSkillImpact]
    skill_gaps_before: List[SkillGap]
    skill_gaps_after: List[SkillGap]
    critical_gaps_before: List[SkillGap]
    critical_gaps_after: List[SkillGap]
    total_gap_before: int
    total_gap_after: int
    total_gap_reduction: int
    critical_gap_before: int
    critical_gap_after: int
    critical_gap_reduction: int
    requirements_closed: List[str]
    critical_requirements_closed: List[str]
    readiness_before: Optional[float]
    readiness_after: Optional[float]
    readiness_delta: Optional[float]
    readiness_before_details: ReadinessResult
    readiness_after_details: ReadinessResult


class ParticipationEligibilityEvidence(TypedDict):
    completed_record_ids: List[str]
    in_progress_record_ids: List[str]
    ignored_future_record_ids: List[str]
    recurring_exception: bool


class AvailabilityEvidence(TypedDict):
    format: str
    available: bool
    self_paced: bool
    next_session_date: Optional[str]
    days_until_next_session: Optional[int]
    valid_session_dates: List[str]


class CandidateEvidence(TypedDict):
    current_role: str
    target_role: Optional[str]
    target_grade: Optional[str]
    audience_match: Optional[Literal["current_role", "target_role", "both"]]
    attained_grade: str
    matched_current_grade: Optional[str]
    prerequisite_checks: List[PrerequisiteCheck]
    history: ParticipationEligibilityEvidence
    availability: AvailabilityEvidence
    skills_are_estimated: bool


class EligibilityResult(TypedDict):
    event_id: str
    title: str
    eligible: bool
    rejection_reasons: List[RejectionReason]
    evidence: CandidateEvidence
    simulation: Optional[EventSimulation]


class CatalogEligibility(TypedDict):
    employee_id: str
    as_of: str
    target: Optional[CareerTarget]
    event_count: int
    eligible_count: int
    rejected_count: int
    eligible_candidates: List[EligibilityResult]
    rejected_events: List[EligibilityResult]


# Step 3 adds preference/scoring contracts; earlier public structures stay intact.
class ScoringEventInput(EligibilityEventInput, total=False):
    type: str
    duration_hours: Union[int, float, str, None]


class HistoryParticipationInput(ParticipationInput, total=False):
    assigned_by: Optional[str]
    feedback_rating: Union[int, float, str, None]
    score: Union[int, float, str, None]


class HistoryEvidence(TypedDict):
    matched_history_count: int
    effective_history_weight: float
    positive_weight: float
    negative_weight: float
    recent_similar_no_shows: int
    recent_similar_completions: int
    rating_observation_count: int
    assessment_observation_count: int
    effective_feedback_weight: float
    feedback_record_count: int
    zero_weight_count: int
    weighted_outcome_sum: float
    weighted_feedback_sum: float
    considered_history_count: int
    excluded_mandatory_count: int
    excluded_status_count: int
    ignored_future_count: int
    zero_similarity_count: int
    unknown_source_count: int
    invalid_rating_count: int
    invalid_assessment_count: int
    missing_rating_count: int
    missing_assessment_count: int
    completion_date_proxy_count: int
    priors: Dict[str, float]
    config_snapshot: Dict[str, object]


class _HistorySignalsRequired(TypedDict):
    compatibility: float
    feedback_signal: float
    evidence: HistoryEvidence


class HistorySignals(_HistorySignalsRequired, total=False):
    # Opt-in backend/debug detail. The default exposes aggregate evidence only.
    record_evidence: List[Dict[str, object]]


class FactorScore(TypedDict):
    raw: float
    normalized: float
    weight: float
    contribution: float


class ScoringEvidence(TypedDict):
    useful_destination_gain: int
    advertised_positive_gain: int
    duration_hours: Optional[float]
    duration_valid: bool
    raw_efficiency: float
    normalization_maxima: Dict[str, float]
    availability_wait_days: int
    normalization_candidate_count: int


class ScoredCandidate(TypedDict):
    event_id: str
    score: float
    factors: Dict[str, FactorScore]
    scoring_evidence: ScoringEvidence


class RankedRecommendation(ScoredCandidate):
    rank: int
    title: str
    simulation: EventSimulation
    evidence: CandidateEvidence
    history_signals: HistorySignals


class BlockedEvent(TypedDict):
    event_id: str
    rejection_codes: List[RejectionCode]


class UsefulBlockedEvent(BlockedEvent):
    total_gap_reduction: int
    critical_gap_reduction: int


class BlockedSummary(TypedDict):
    rejection_counts: Dict[str, int]
    event_rejections: List[BlockedEvent]
    uncovered_target_gaps: List[SkillGap]
    useful_blocked_events: List[UsefulBlockedEvent]


class RecommendationResult(TypedDict):
    employee_id: str
    as_of: str
    status: Literal["ok", "no_eligible_recommendations", "no_next_grade", "target_satisfied", "invalid_target_requirements"]
    target: Optional[CareerTarget]
    career_readiness: Optional[ReadinessResult]
    skill_gaps: List[SkillGap]
    career_state: CareerState
    candidate_count: int
    recommendation_count: int
    recommendations: List[RankedRecommendation]
    blocked_summary: Optional[BlockedSummary]
