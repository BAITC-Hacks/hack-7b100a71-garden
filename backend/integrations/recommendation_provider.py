"""Thin repository-to-engine adapter; no scoring, HTTP or persistence logic."""

from backend.ai.explanations import enrich_recommendations
from backend.integrations.engine_inputs import history_for_engine
from backend.recommendation.engine import recommend


class RecommendationProvider:
    def __init__(self, *, use_openai=True, environ=None, transport=None):
        self.use_openai = use_openai
        self.environ = environ
        self.transport = transport

    def recommend(self, employee_id, view):
        employee = view.get_employee(employee_id)
        if employee is None:
            raise ValueError("Employee is absent from the supplied repository snapshot")
        result = recommend(
            employee.model_dump(mode="json"),
            [profile.model_dump(mode="json") for profile in view.get_all_role_profiles()],
            [event.model_dump(mode="json") for event in view.get_all_events()],
            history_for_engine(view.get_employee_history(employee_id), view.get_runtime_completion_ids()),
            as_of=view.as_of_date,
        )
        return enrich_recommendations(
            result, preferred_language=employee.preferred_language,
            use_openai=self.use_openai, environ=self.environ, transport=self.transport,
        )
