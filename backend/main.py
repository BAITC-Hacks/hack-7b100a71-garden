"""Application factory: no file IO or global state initialization on import."""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.config import Settings
from backend.data.repository import DatasetRepository
from backend.errors import AppError
from backend.services.activity_service import ActivityService
from backend.services.dataset_service import DatasetService
from backend.services.recommendation_service import RecommendationService

logger = logging.getLogger(__name__)


def create_app(settings=None, repository=None, recommendation_provider=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(application):
        active_repository = repository
        if active_repository is None:
            if settings.database_url:
                from backend.data.postgres_repository import PostgresRepository
                active_repository = PostgresRepository(settings.database_url)
                active_repository.initialize(settings.data_dir, settings.runtime_state_path)
            else:
                active_repository = DatasetRepository.from_directory(
                    settings.data_dir, settings.runtime_state_path
                )
        application.state.repository = active_repository
        application.state.activity_service = ActivityService(active_repository)
        application.state.dataset_service = DatasetService(active_repository)
        application.state.recommendation_service = RecommendationService(
            active_repository, recommendation_provider,
            settings.recommendation_timeout_seconds,
        )
        yield

    application = FastAPI(title="Career Quest API", version="0.2.0", lifespan=lifespan)
    application.state.settings = settings
    application.add_middleware(
        CORSMiddleware, allow_origins=list(settings.cors_origins),
        allow_credentials=False, allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(status_code=exc.status_code, headers=headers,
                            content={"error": {"code": exc.code, "message": exc.message,
                                               "details": exc.details}})

    @application.exception_handler(RequestValidationError)
    async def request_error_handler(request: Request, exc: RequestValidationError):
        # Exclude input values and context; tokens/PII must not appear in validation errors.
        details = [{"location": ".".join(str(part) for part in error["loc"]),
                    "message": error["msg"], "code": error["type"]}
                   for error in exc.errors()]
        return JSONResponse(status_code=422, content={"error": {
            "code": "invalid_request", "message": "Request validation failed", "details": details}})

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code, headers=exc.headers,
                            content={"error": {"code": "http_error",
                                               "message": str(exc.detail), "details": []}})

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        logger.error("Unhandled API error", exc_info=(type(exc), exc, exc.__traceback__))
        return JSONResponse(status_code=500, content={"error": {
            "code": "internal_error", "message": "An unexpected server error occurred", "details": []}})

    @application.get("/health", tags=["health"])
    def health(request: Request):
        view = request.app.state.repository.view()
        return {"data": {"status": "ok", "version": view.version,
                         "as_of_date": view.as_of_date, "counts": view.counts()}}

    from backend.api import router
    application.include_router(router)
    return application


app = create_app()
