"""Timeout, result validation and versioned cache around the external engine."""
import asyncio
import inspect
import logging
from threading import RLock

from starlette.concurrency import run_in_threadpool

from backend.errors import AppError
from backend.integrations.recommendations import RecommendationCoverage, RecommendationResult

logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(self, repository, provider=None, timeout_seconds: float = 9.0):
        self.repository = repository
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self._cache = {}
        self._cache_version = None
        self._summary_attempted = False
        self._summary = None
        self._lock = RLock()

    def _version_cache(self, version):
        if self._cache_version != version:
            self._cache.clear()
            self._cache_version = version
            self._summary_attempted = False
            self._summary = None

    async def recommend(self, employee_id: str, view=None) -> dict:
        view = self.repository.view() if view is None else view
        if view.get_employee(employee_id) is None:
            raise AppError("employee_not_found", "Employee not found", 404)
        if self.provider is None:
            raise AppError("recommendation_unavailable", "Recommendation engine is not connected", 503)
        if self.repository.version != view.version:
            raise AppError("dataset_changed", "Employee data changed while recommendations were generated; retry", 409)
        with self._lock:
            self._version_cache(view.version)
            cached = self._cache.get(employee_id)
            if cached is not None:
                return {**cached.model_dump(mode="json"), "version": view.version}

        async def invoke():
            method = self.provider.recommend
            if inspect.iscoroutinefunction(method):
                return await method(employee_id, view)
            value = await run_in_threadpool(method, employee_id, view)
            return await value if inspect.isawaitable(value) else value

        try:
            raw = await asyncio.wait_for(invoke(), timeout=self.timeout_seconds)
            result = RecommendationResult.model_validate(raw)
            data = result.root
            if data["employee_id"] != employee_id:
                raise ValueError("engine returned a different employee")
            if data["as_of"] != view.as_of_date.isoformat():
                raise ValueError("engine returned a different snapshot date")
            if data["target"] and not view.get_role_profile(data["target"]["role"], data["target"]["grade"]):
                raise ValueError("engine returned an unknown target")
            event_ids = set()
            for item in data["recommendations"]:
                event = view.get_event(item["event_id"])
                if event is None or event.mandatory or item["event_id"] in event_ids:
                    raise ValueError("engine returned an unknown, mandatory or duplicate event")
                event_ids.add(item["event_id"])
                if item["simulation"]["event_id"] != item["event_id"]:
                    raise ValueError("engine simulation belongs to a different event")
                if any(view.get_skill(change["skill_id"]) is None for change in item["simulation"]["skill_impact"]):
                    raise ValueError("engine returned an unknown projected skill")
        except asyncio.TimeoutError as exc:
            raise AppError("recommendation_timeout", "Recommendation engine exceeded its time limit", 504) from exc
        except Exception as exc:
            logger.exception("Recommendation provider failed for employee %s", employee_id)
            raise AppError("invalid_recommendation_result", "Recommendation engine failed to produce a valid result", 502) from exc
        if self.repository.version != view.version:
            raise AppError("dataset_changed", "Employee data changed while recommendations were generated; retry", 409)
        with self._lock:
            self._version_cache(view.version)
            self._cache[employee_id] = result.model_copy(deep=True)
        return {**result.model_dump(mode="json"), "version": view.version}

    def coverage(self, view) -> dict:
        """Use a fast deterministic summary hook or known cached recommendations.

        This never calls recommend() in a loop or requests AI explanations.
        """
        total = len(view.get_all_employees())
        with self._lock:
            self._version_cache(view.version)
            summary_method = getattr(self.provider, "coverage", None)
            if summary_method is not None and not self._summary_attempted:
                self._summary_attempted = True
                try:
                    if inspect.iscoroutinefunction(summary_method):
                        raise ValueError("coverage must be synchronous deterministic work")
                    summary = RecommendationCoverage.model_validate(summary_method(view))
                    if not 0 <= summary.without_next_step_count <= summary.evaluated_count <= total:
                        raise ValueError("coverage counts are outside the dataset bounds")
                    self._summary = summary
                except Exception:
                    logger.exception("Recommendation coverage hook failed; using known cached results")
            summary = self._summary
            results = list(self._cache.values())
        if summary is not None:
            return {"available": True, "count": summary.without_next_step_count,
                    "evaluated_count": summary.evaluated_count,
                    "pending_count": total - summary.evaluated_count,
                    "complete": summary.evaluated_count == total}
        evaluated = len(results)
        return {
            "available": self.provider is not None,
            "count": sum(not result.root["recommendations"] for result in results) if evaluated else None,
            "evaluated_count": evaluated,
            "pending_count": total - evaluated,
            "complete": evaluated == total and self.provider is not None,
        }
