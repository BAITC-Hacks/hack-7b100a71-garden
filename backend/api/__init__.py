"""HTTP API routes."""
"""The public FastAPI router; business logic lives in services."""

from fastapi import APIRouter

from backend.api import activities, datasets, employees, events, hr


router = APIRouter()
for child_router in (employees.router, events.router, activities.router, datasets.router, hr.router):
    router.include_router(child_router)
