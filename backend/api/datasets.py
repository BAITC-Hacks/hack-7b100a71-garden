"""Bounded multipart imports using the official dataset file names."""

from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from backend.api.dependencies import get_dataset_service
from backend.errors import AppError
from backend.models.api import ApiResponse, ValidationResult
from backend.security import current_hr_identity


router = APIRouter(prefix="/datasets", tags=["datasets"], dependencies=[Depends(current_hr_identity)])


async def uploaded_files(
    request: Request,
    employees_file: Optional[UploadFile] = File(default=None),
    activity_history_file: Optional[UploadFile] = File(default=None),
    events_file: Optional[UploadFile] = File(default=None),
    skills_file: Optional[UploadFile] = File(default=None),
) -> Dict[str, bytes]:
    uploads = {
        "employees.json": employees_file,
        "activity_history.csv": activity_history_file,
        "events.json": events_file,
        "skills.json": skills_file,
    }
    if not any(item is not None for item in uploads.values()):
        raise AppError("missing_upload", "Provide at least one dataset file.")

    maximum = request.app.state.settings.upload_max_bytes
    total = 0
    files = {}
    try:
        for name, item in uploads.items():
            if item is None:
                continue
            content = await item.read(maximum - total + 1)
            total += len(content)
            if total > maximum:
                raise AppError(
                    "upload_too_large",
                    "The combined dataset upload exceeds the configured size limit.",
                    status_code=413,
                    details=[{"max_bytes": maximum}],
                )
            if not content:
                raise AppError("empty_upload", "An uploaded file is empty.", details=[{"file": name}])
            files[name] = content
    finally:
        for item in uploads.values():
            if item is not None:
                await item.close()
    return files


@router.post("/validate", response_model=ApiResponse[ValidationResult], response_model_exclude_unset=True)
async def validate_dataset(
    mode: Literal["append", "replace"] = Query(default="append"),
    files: Dict[str, bytes] = Depends(uploaded_files),
    service: Any = Depends(get_dataset_service),
) -> Dict[str, Any]:
    result = await run_in_threadpool(service.validate, files, mode)
    return {"data": result}


@router.post("/upload", response_model=ApiResponse[Dict[str, Any]], response_model_exclude_unset=True)
async def upload_dataset(
    mode: Literal["append", "replace"] = Query(default="append"),
    files: Dict[str, bytes] = Depends(uploaded_files),
    service: Any = Depends(get_dataset_service),
) -> Dict[str, Any]:
    result = await run_in_threadpool(service.upload, files, mode)
    return {"data": result}
