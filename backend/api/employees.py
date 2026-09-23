"""Employee profile, history and recommendation access."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from backend.api.dependencies import get_recommendation_service, get_view, paginated, snapshot_meta
from backend.errors import AppError
from backend.models.api import ApiResponse, EmployeeDetail
from backend.models.domain import ActivityRecord, Employee
from backend.security import Identity, current_hr_identity, current_identity, require_employee_or_hr


router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("", response_model=ApiResponse[List[Employee]], response_model_exclude_unset=True)
def list_employees(
    department: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
    grade: Optional[str] = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    identity: Identity = Depends(current_hr_identity),
    view: Any = Depends(get_view),
) -> Dict[str, Any]:
    rows = [
        employee
        for employee in view.get_all_employees()
        if (department is None or employee.department == department)
        and (role is None or employee.role == role)
        and (grade is None or employee.grade == grade)
    ]
    return paginated(rows, view, offset, limit)


@router.get("/{employee_id}", response_model=ApiResponse[EmployeeDetail], response_model_exclude_unset=True)
def get_employee(
    employee_id: str,
    identity: Identity = Depends(current_identity),
    view: Any = Depends(get_view),
) -> Dict[str, Any]:
    require_employee_or_hr(identity, employee_id)
    employee = view.get_employee(employee_id)
    if employee is None:
        raise AppError("employee_not_found", "Employee was not found.", status_code=404)
    return {
        "data": {
            "employee": employee,
            "role_profile": view.get_role_profile(employee.role, employee.grade),
            "effective_skills": view.get_effective_skills(employee_id),
        },
        "meta": snapshot_meta(view),
    }


@router.get(
    "/{employee_id}/history",
    response_model=ApiResponse[List[ActivityRecord]],
    response_model_exclude_unset=True,
)
def get_history(
    employee_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    identity: Identity = Depends(current_identity),
    view: Any = Depends(get_view),
) -> Dict[str, Any]:
    require_employee_or_hr(identity, employee_id)
    if view.get_employee(employee_id) is None:
        raise AppError("employee_not_found", "Employee was not found.", status_code=404)
    return paginated(view.get_employee_history(employee_id), view, offset, limit)


@router.get(
    "/{employee_id}/recommendations",
    response_model=ApiResponse[Dict[str, Any]],
    response_model_exclude_unset=True,
)
async def get_recommendations(
    employee_id: str,
    identity: Identity = Depends(current_identity),
    view: Any = Depends(get_view),
    service: Any = Depends(get_recommendation_service),
) -> Dict[str, Any]:
    require_employee_or_hr(identity, employee_id)
    if view.get_employee(employee_id) is None:
        raise AppError("employee_not_found", "Employee was not found.", status_code=404)
    return {"data": await service.recommend(employee_id)}
