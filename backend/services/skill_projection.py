"""Canonical skill arithmetic; this module does not choose career targets or events."""
from typing import Dict, Iterable, Mapping, Sequence

from backend.models.domain import ActivityRecord, Employee, Event


def apply_gain(current: int, gain: int, max_level: int) -> int:
    # An introductory course cannot reduce an already higher assessed skill.
    return max(current, min(current + gain, max_level))


def project_skills(employee: Employee, history: Iterable[ActivityRecord],
                   events: Mapping[str, Event], live_completed_ids: Sequence[str] = ()) -> Dict[str, int]:
    levels = dict(employee.skills)
    completed = [record for record in history if record.status == "completed"]
    live_order = {record_id: index for index, record_id in enumerate(live_completed_ids)}
    for record in sorted(completed, key=lambda item: (
        item.completed_on or item.date, item.record_id in live_order,
        live_order.get(item.record_id, -1), item.record_id,
    )):
        completion_date = record.completed_on or record.date
        after_review = completion_date > employee.last_review_date
        explicit_same_day_completion = (completion_date == employee.last_review_date
                                        and record.record_id in live_completed_ids)
        if not (after_review or explicit_same_day_completion):
            continue
        event = events.get(record.event_id)
        if event is None:
            continue
        for change in event.develops_skills:
            levels[change.skill_id] = apply_gain(levels.get(change.skill_id, 0),
                                                 change.gain, change.max_level)
    return levels
