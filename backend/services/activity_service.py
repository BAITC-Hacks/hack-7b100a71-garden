"""Completion changes participation state once and leaves assessed skills untouched."""
import hashlib
import json
from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import uuid4

from backend.data.repository import DatasetRepository, MutableState
from backend.errors import AppError
from backend.models.domain import ActivityRecord
from backend.integrations.engine_inputs import history_for_engine
from backend.recommendation.career import build_career_state
from backend.recommendation.eligibility import evaluate_event


class ActivityService:
    def __init__(self, repository: DatasetRepository, *, clock: Optional[Callable[[], datetime]] = None):
        self.repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def complete(self, event_id: str, employee_id: str, idempotency_key: str,
                 record_id: Optional[str] = None, score: Optional[int] = None,
                 feedback_rating: Optional[int] = None) -> dict:
        if not isinstance(idempotency_key, str) or not idempotency_key.strip() or len(idempotency_key) > 128:
            raise AppError("invalid_idempotency_key", "Idempotency-Key must contain 1 to 128 characters")
        request = {"event_id": event_id, "employee_id": employee_id,
                   "record_id": record_id, "score": score, "feedback_rating": feedback_rating}
        fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        receipt_key = hashlib.sha256(json.dumps([employee_id, idempotency_key]).encode()).hexdigest()

        def operation(state: MutableState):
            receipt = state.receipts.get(receipt_key)
            if receipt is not None:
                if receipt["fingerprint"] != fingerprint:
                    raise AppError("idempotency_conflict", "This Idempotency-Key was used for a different request", 409)
                state.dirty = False
                return {**receipt["result"], "replayed": True}
            view = state.view()
            employee = view.get_employee(employee_id)
            if employee is None:
                raise AppError("employee_not_found", "Employee not found", 404)
            event = view.get_event(event_id)
            if event is None:
                raise AppError("event_not_found", "Event not found", 404)
            history = [row for row in view.get_employee_history(employee_id) if row.event_id == event_id]
            previous = [row for row in history if row.status == "completed"]
            recurring = event_id == "EV_036" or (event.mandatory and event.type == "compliance")
            if previous and not recurring:
                raise AppError("already_completed", "This development event has already been completed", 409)
            if event_id == "EV_036" and any(
                (row.completed_on or (row.completed_at.date() if row.completed_at is not None else row.date))
                == view.as_of_date for row in previous
            ):
                raise AppError("session_already_completed", "This club session was already completed on the dataset date", 409)

            selected = None
            if record_id is not None:
                selected = next((row for row in history if row.record_id == record_id), None)
                if selected is None:
                    raise AppError("activity_record_not_found", "Activity record not found for this employee and event", 404)
                if selected.status not in {"in_progress", "overdue"}:
                    raise AppError("invalid_activity_status", "Only an active or overdue record can transition to completed", 409)
            else:
                active = [row for row in history if row.status in {"in_progress", "overdue"}]
                if len(active) > 1:
                    raise AppError("ambiguous_activity", "Multiple assignments exist; supply record_id", 409)
                selected = active[0] if active else None

            before = view.get_effective_skills(employee_id)
            if selected is None:
                if event.mandatory:
                    raise AppError("assignment_required", "A mandatory event requires an existing active assignment", 409)
                current_role_match = employee.role in event.target_roles
                goal = employee.career_goal
                target_role_match = goal is not None and goal.target_role in event.target_roles
                if (not (current_role_match or target_role_match)
                        or employee.grade not in event.target_grades):
                    raise AppError("event_audience_mismatch", "Event does not target the current or explicit destination role at the attained grade")
                unmet = [{"skill_id": skill_id, "required": required,
                          "actual": before.get(skill_id, 0)}
                         for skill_id, required in event.prerequisites.items()
                         if before.get(skill_id, 0) < required]
                if unmet:
                    raise AppError("prerequisites_not_met", "Event prerequisites are not met", details=unmet)
                if not current_role_match:
                    # Extending admission to an explicit destination must use
                    # the existing engine rules, not create a second policy.
                    history_input = history_for_engine(
                        view.get_employee_history(employee_id), view.get_runtime_completion_ids(),
                    )
                    employee_input = employee.model_dump(mode="json")
                    career_state = build_career_state(
                        employee_input,
                        [profile.model_dump(mode="json") for profile in view.get_all_role_profiles()],
                        [item.model_dump(mode="json") for item in view.get_all_events()],
                        history_input, as_of=view.as_of_date,
                    )
                    target_profile = view.get_role_profile(goal.target_role, goal.target_grade)
                    admission = evaluate_event(
                        employee_input, career_state, target_profile.model_dump(mode="json"),
                        event.model_dump(mode="json"), history_input, as_of=view.as_of_date,
                    )
                    if not admission["eligible"]:
                        raise AppError("event_not_eligible", "Destination-role event is not eligible",
                                       details=admission["rejection_reasons"])
            if score is not None and event.type not in {"course", "certification", "compliance"}:
                raise AppError("score_not_supported", "Scores are only supported for courses, certifications and compliance")

            if selected is None:
                known_ids = {row.record_id for row in state.dataset.history}
                new_id = "RUNTIME-" + uuid4().hex
                while new_id in known_ids:
                    new_id = "RUNTIME-" + uuid4().hex
                selected_data = {
                    "record_id": new_id, "employee_id": employee_id, "event_id": event_id,
                    "date": view.as_of_date, "due_date": None, "assigned_by": "self",
                }
            else:
                selected_data = selected.model_dump()
            recorded_at = self._clock()
            if (not isinstance(recorded_at, datetime) or recorded_at.tzinfo is None
                    or recorded_at.utcoffset() is None):
                raise AppError("invalid_completion_clock", "Completion clock must return an aware timestamp", 503)
            # The transaction serializes all writes, including equal or
            # backwards wall-clock instants. Legacy IDs preserve the old order.
            next_sequence = max(
                [len(state.completed_record_ids)] +
                [row.runtime_sequence or 0 for row in state.dataset.history]
            ) + 1
            selected_data.update(status="completed", completion_pct=100,
                                 score=score,
                                 feedback_rating=(feedback_rating if feedback_rating is not None
                                                  else selected_data.get("feedback_rating")),
                                 completed_on=view.as_of_date,
                                 completed_at=recorded_at.astimezone(timezone.utc),
                                 runtime_sequence=next_sequence)
            completed = ActivityRecord.model_validate(selected_data)
            if selected is None:
                state.dataset.history.append(completed)
            else:
                state.dataset.history = [completed if row.record_id == completed.record_id else row
                                         for row in state.dataset.history]
            state.completed_record_ids.append(completed.record_id)
            after = state.view().get_effective_skills(employee_id)
            changes = [
                {"skill_id": gain.skill_id, "before": before.get(gain.skill_id, 0),
                 "after": after.get(gain.skill_id, 0),
                 "gain": after.get(gain.skill_id, 0) - before.get(gain.skill_id, 0),
                 "event_gain": gain.gain, "max_level": gain.max_level}
                for gain in event.develops_skills
            ]
            result = {"activity": completed.model_dump(mode="json"),
                      "effective_skills": after, "skill_changes": changes,
                      "version": state.version, "replayed": False}
            state.receipts[receipt_key] = {"fingerprint": fingerprint, "result": result}
            return result

        return self.repository.mutate(operation)


def effective_skills(repository, employee_id):
    """Compatibility helper; delegates to the single canonical projection."""
    return repository.get_effective_skills(employee_id)
