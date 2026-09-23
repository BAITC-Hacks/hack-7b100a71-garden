"""Public domain contracts shared by API, repository and recommendation engine."""

from .domain import (
    GRADES,
    ActivityRecord,
    ActivityStatus,
    AssignedBy,
    CareerGoal,
    Dataset,
    DatasetMeta,
    DomainModel,
    Employee,
    EmployeesDocument,
    Event,
    EventsDocument,
    Grade,
    RoleProfile,
    Skill,
    SkillGain,
    SkillsDocument,
    ValidationIssue,
)

__all__ = [
    "GRADES", "ActivityRecord", "ActivityStatus", "AssignedBy", "CareerGoal",
    "Dataset", "DatasetMeta", "DomainModel", "Employee", "EmployeesDocument",
    "Event", "EventsDocument", "Grade", "RoleProfile", "Skill", "SkillGain",
    "SkillsDocument", "ValidationIssue",
]
