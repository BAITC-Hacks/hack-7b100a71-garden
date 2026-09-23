"""API envelopes and client input; source dataset models live in domain.py."""

from datetime import date
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.domain import Employee, RoleProfile


T = TypeVar("T")


class ResponseMeta(BaseModel):
    version: int
    as_of_date: date
    total: Optional[int] = None
    offset: Optional[int] = None
    limit: Optional[int] = None


class ApiResponse(BaseModel, Generic[T]):
    data: T
    meta: Optional[ResponseMeta] = None


class EmployeeDetail(BaseModel):
    employee: Employee
    role_profile: Optional[RoleProfile]
    effective_skills: Dict[str, int]


class CompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: str = Field(strict=True, min_length=1)
    record_id: Optional[str] = Field(default=None, strict=True, min_length=1)
    score: Optional[int] = Field(default=None, strict=True, ge=0, le=100)
    feedback_rating: Optional[int] = Field(default=None, strict=True, ge=1, le=5)

    @field_validator("employee_id", "record_id")
    @classmethod
    def identifiers_have_content(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("Identifier must contain non-whitespace characters.")
        return value


class ValidationResult(BaseModel):
    valid: bool
    counts: Dict[str, int]
    errors: List[Dict[str, Any]]
    mode: str
    version: int
