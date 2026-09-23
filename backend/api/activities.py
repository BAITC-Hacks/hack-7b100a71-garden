"""Idempotent activity completion."""

from typing import Any, Dict

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_activity_service, idempotency_key
from backend.models.api import ApiResponse, CompletionRequest
from backend.security import Identity, current_identity, require_employee_or_hr


router = APIRouter(prefix="/activities", tags=["activities"])


@router.post(
    "/{event_id}/complete", response_model=ApiResponse[Dict[str, Any]], response_model_exclude_unset=True
)
def complete_activity(
    event_id: str,
    payload: CompletionRequest,
    identity: Identity = Depends(current_identity),
    key: str = Depends(idempotency_key),
    service: Any = Depends(get_activity_service),
) -> Dict[str, Any]:
    require_employee_or_hr(identity, payload.employee_id)
    return {
        "data": service.complete(
            event_id=event_id,
            employee_id=payload.employee_id,
            idempotency_key=key,
            record_id=payload.record_id,
            score=payload.score,
            feedback_rating=payload.feedback_rating,
        )
    }
