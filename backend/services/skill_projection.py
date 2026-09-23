"""Backend adapter for the engine's sole effective-skills reconstruction."""
from datetime import date
from typing import Dict, Iterable, Mapping, Sequence

from backend.models.domain import ActivityRecord, Employee, Event
from backend.integrations.engine_inputs import history_for_engine
from backend.recommendation.skills import reconstruct_effective_skills


def project_skills(employee: Employee, history: Iterable[ActivityRecord],
                   events: Mapping[str, Event], live_completed_ids: Sequence[str] = (),
                   *, as_of: date) -> Dict[str, int]:
    reconstruction = reconstruct_effective_skills(
        employee.model_dump(mode="json"),
        [event.model_dump(mode="json") for event in events.values()],
        history_for_engine(history, live_completed_ids), as_of=as_of,
    )
    return reconstruction["effective_skills"]
