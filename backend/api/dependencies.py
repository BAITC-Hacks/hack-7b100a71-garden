"""Shared API access to application state and snapshot response metadata."""

from typing import Any, Dict, Sequence

from fastapi import Header, Request

from backend.errors import AppError


def get_view(request: Request) -> Any:
    return request.app.state.repository.view()


def get_activity_service(request: Request) -> Any:
    return request.app.state.activity_service


def get_dataset_service(request: Request) -> Any:
    return request.app.state.dataset_service


def get_recommendation_service(request: Request) -> Any:
    return request.app.state.recommendation_service


def snapshot_meta(view: Any) -> Dict[str, Any]:
    return {"version": view.version, "as_of_date": view.as_of_date}


def paginated(rows: Sequence[Any], view: Any, offset: int, limit: int) -> Dict[str, Any]:
    return {
        "data": rows[offset : offset + limit],
        "meta": {**snapshot_meta(view), "total": len(rows), "offset": offset, "limit": limit},
    }


def idempotency_key(
    value: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=128),
) -> str:
    if not value.strip():
        raise AppError("invalid_idempotency_key", "Idempotency-Key must not be blank.")
    return value
