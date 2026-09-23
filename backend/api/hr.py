"""Aggregated HR reporting without individual employee rankings."""

from typing import Any, Dict

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_recommendation_service, get_view, snapshot_meta
from backend.models.api import ApiResponse
from backend.security import current_hr_identity
from backend.services.hr_service import build_hr_analytics


router = APIRouter(prefix="/hr", tags=["hr"], dependencies=[Depends(current_hr_identity)])


@router.get("/analytics", response_model=ApiResponse[Dict[str, Any]], response_model_exclude_unset=True)
def hr_analytics(
    view: Any = Depends(get_view), service: Any = Depends(get_recommendation_service)
) -> Dict[str, Any]:
    return {
        "data": build_hr_analytics(view, service.coverage(view)),
        "meta": snapshot_meta(view),
    }
