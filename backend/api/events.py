"""Authenticated event and skill catalogs."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from backend.api.dependencies import get_view, paginated, snapshot_meta
from backend.errors import AppError
from backend.models.api import ApiResponse
from backend.models.domain import Event, RoleProfile, Skill
from backend.security import current_identity


router = APIRouter(tags=["catalogs"], dependencies=[Depends(current_identity)])


@router.get("/events", response_model=ApiResponse[List[Event]], response_model_exclude_unset=True)
def list_events(
    role: Optional[str] = Query(default=None),
    grade: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None, alias="type"),
    event_format: Optional[str] = Query(default=None, alias="format"),
    mandatory: Optional[bool] = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    view: Any = Depends(get_view),
) -> Dict[str, Any]:
    rows = [
        event
        for event in view.get_all_events()
        if (role is None or role in event.target_roles)
        and (grade is None or grade in event.target_grades)
        and (event_type is None or event.type == event_type)
        and (event_format is None or event.format == event_format)
        and (mandatory is None or event.mandatory == mandatory)
    ]
    return paginated(rows, view, offset, limit)


@router.get("/events/{event_id}", response_model=ApiResponse[Event], response_model_exclude_unset=True)
def get_event(event_id: str, view: Any = Depends(get_view)) -> Dict[str, Any]:
    event = view.get_event(event_id)
    if event is None:
        raise AppError("event_not_found", "Event was not found.", status_code=404)
    return {"data": event, "meta": snapshot_meta(view)}


@router.get("/skills", response_model=ApiResponse[List[Skill]], response_model_exclude_unset=True)
def list_skills(
    skill_type: Optional[str] = Query(default=None, alias="type"),
    category: Optional[str] = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    view: Any = Depends(get_view),
) -> Dict[str, Any]:
    rows = [
        skill
        for skill in view.get_all_skills()
        if (skill_type is None or skill.type == skill_type)
        and (category is None or skill.category == category)
    ]
    return paginated(rows, view, offset, limit)


@router.get("/skills/{skill_id}", response_model=ApiResponse[Skill], response_model_exclude_unset=True)
def get_skill(skill_id: str, view: Any = Depends(get_view)) -> Dict[str, Any]:
    skill = view.get_skill(skill_id)
    if skill is None:
        raise AppError("skill_not_found", "Skill was not found.", status_code=404)
    return {"data": skill, "meta": snapshot_meta(view)}


@router.get("/role-profiles", response_model=ApiResponse[List[RoleProfile]], response_model_exclude_unset=True)
def list_role_profiles(
    role: Optional[str] = Query(default=None),
    grade: Optional[str] = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    view: Any = Depends(get_view),
) -> Dict[str, Any]:
    rows = [
        profile
        for profile in view.get_all_role_profiles()
        if (role is None or profile.role == role)
        and (grade is None or profile.grade == grade)
    ]
    return paginated(rows, view, offset, limit)


@router.get(
    "/role-profiles/{role}/{grade}",
    response_model=ApiResponse[RoleProfile],
    response_model_exclude_unset=True,
)
def get_role_profile(role: str, grade: str, view: Any = Depends(get_view)) -> Dict[str, Any]:
    profile = view.get_role_profile(role, grade)
    if profile is None:
        raise AppError("role_profile_not_found", "Role and grade profile was not found.", status_code=404)
    return {"data": profile, "meta": snapshot_meta(view)}
