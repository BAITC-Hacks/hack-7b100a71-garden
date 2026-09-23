"""Typed contracts for the official documents and the application snapshot.

Strict integer levels reject booleans, strings and fractional skill assessments.
"""

import re
from datetime import date
from typing import Annotated, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

GRADES: Tuple[str, ...] = ("Junior", "Middle", "Senior", "Lead")
Grade = Literal["Junior", "Middle", "Senior", "Lead"]
ActivityStatus = Literal[
    "completed", "in_progress", "dropped", "no_show", "declined", "overdue"
]
AssignedBy = Literal["self", "manager", "hr"]
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
SkillLevel = Annotated[int, Field(strict=True, ge=0, le=5)]
Percentage = Annotated[int, Field(strict=True, ge=0, le=100)]


def _iso_date(value):
    if type(value) is date:
        return value
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("expected a date in YYYY-MM-DD format")
    return value


ISODate = Annotated[date, BeforeValidator(_iso_date)]


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class DatasetMeta(DomainModel):
    dataset: NonEmptyString
    version: NonEmptyString
    as_of_date: ISODate


class CareerGoal(DomainModel):
    target_role: NonEmptyString
    target_grade: Grade


class Employee(DomainModel):
    employee_id: NonEmptyString
    full_name: NonEmptyString
    department: NonEmptyString
    role: NonEmptyString
    grade: Grade
    manager_id: Optional[NonEmptyString]
    hire_date: ISODate
    tenure_months: int = Field(strict=True, ge=0)
    work_format: Literal["office", "hybrid", "remote"]
    preferred_language: Literal["kk", "ru", "en"]
    career_goal: Optional[CareerGoal]
    skills: Dict[NonEmptyString, SkillLevel]
    last_review_date: ISODate


class Skill(DomainModel):
    skill_id: NonEmptyString
    name: NonEmptyString
    type: Literal["hard", "soft"]
    category: NonEmptyString
    description: NonEmptyString


class RoleProfile(DomainModel):
    role: NonEmptyString
    grade: Grade
    required_skills: Dict[NonEmptyString, SkillLevel]
    critical_skills: List[NonEmptyString]


class SkillGain(DomainModel):
    skill_id: NonEmptyString
    gain: int = Field(strict=True, ge=1)
    max_level: SkillLevel


class Event(DomainModel):
    event_id: NonEmptyString
    title: NonEmptyString
    description: NonEmptyString
    type: Literal[
        "compliance", "onboarding", "course", "workshop", "mentoring",
        "certification", "meetup"
    ]
    format: Literal["online", "offline", "self_paced"]
    duration_hours: float = Field(strict=True, ge=0, allow_inf_nan=False)
    mandatory: bool = Field(strict=True)
    target_roles: List[NonEmptyString]
    target_grades: List[Grade]
    develops_skills: List[SkillGain]
    prerequisites: Dict[NonEmptyString, SkillLevel]
    upcoming_sessions: List[ISODate]


class ActivityRecord(DomainModel):
    record_id: NonEmptyString
    employee_id: NonEmptyString
    event_id: NonEmptyString
    date: ISODate
    due_date: Optional[ISODate] = None
    status: ActivityStatus
    completion_pct: Percentage
    score: Optional[Percentage] = None
    feedback_rating: Optional[Annotated[int, Field(strict=True, ge=1, le=5)]] = None
    assigned_by: AssignedBy
    # Runtime extension: the official self-paced date is enrollment/assignment.
    completed_on: Optional[ISODate] = None


class EmployeesDocument(DomainModel):
    meta: DatasetMeta
    employees: List[Employee]


class SkillsDocument(DomainModel):
    meta: DatasetMeta
    proficiency_scale: Dict[str, NonEmptyString]
    skills: List[Skill]
    role_profiles: List[RoleProfile]


class EventsDocument(DomainModel):
    meta: DatasetMeta
    events: List[Event]


class Dataset(DomainModel):
    meta: DatasetMeta
    proficiency_scale: Dict[str, NonEmptyString]
    employees: List[Employee]
    skills: List[Skill]
    role_profiles: List[RoleProfile]
    events: List[Event]
    history: List[ActivityRecord]


class ValidationIssue(DomainModel):
    code: str
    location: str
    message: str
