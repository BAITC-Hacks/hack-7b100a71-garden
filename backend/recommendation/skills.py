"""Reconstruct review-time skills without persistence or application models.

Legacy history dates are participation dates, not completion timestamps. Replay
is therefore an estimate whenever a skill-bearing legacy record is applied.
``completed_at`` is an optional adapter extension: date/datetime objects or ISO
strings are accepted. Review/snapshot boundaries use its stated calendar date,
including the whole snapshot day. Timestamp ordering uses UTC; naive timestamps
are interpreted as UTC for ordering only. Date-only values use midnight and
record IDs break ties, without claiming that this recovers completion order.

Trusted runtime records additionally carry completed_on (logical snapshot day)
and runtime_sequence (transaction order). Their real completed_at timestamp is
retained, but is not confused with the fixture's logical calendar. Runtime
operations follow the loaded assessment, including on its calendar day.
"""

from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timezone
from typing import Union

from .config import DEFAULT_CONFIG, RecommendationConfig
from .contracts import RecommendationInputError, SkillsReconstruction


def _error(code, message):
    raise RecommendationInputError(code, message)


def _identifier(value, field):
    if not isinstance(value, str) or not value.strip():
        _error("invalid_identifier", "{} must be a nonempty string".format(field))
    return value


def _require_sequence(value, field, code):
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _error(code, "{} must be a sequence of record mappings, not a dataset wrapper".format(field))


def _calendar_date(value, field):
    if isinstance(value, datetime):
        _error("invalid_date", "{} must be a calendar date, not a timestamp".format(field))
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    _error("invalid_date", "{} must be an ISO calendar date".format(field))


def _completion_time(value, field):
    """Return (stated date, UTC order key, includes time of day)."""
    parsed = value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            try:
                parsed = datetime.fromisoformat(
                    value[:-1] + "+00:00" if value.endswith("Z") else value
                )
            except ValueError:
                _error("invalid_date", "{} must be an ISO date or datetime".format(field))
    if isinstance(parsed, datetime):
        instant = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        return parsed.date(), instant.astimezone(timezone.utc), True
    if isinstance(parsed, date):
        return parsed, datetime.combine(parsed, time.min, timezone.utc), False
    _error("invalid_date", "{} must be an ISO date or datetime".format(field))


def _participation_timing(record):
    """Shared date boundary for reconstruction, admission and history signals.

    The adapter alone supplies runtime_sequence. A positive sequence is proof
    of a persisted operation after loading the assessment, not an input an HTTP
    client or dataset upload may choose. Legacy rows retain their old policy.
    Return participation day, completion day, UTC instant, precision, sequence.
    """
    participation, participation_order, participation_has_time = _completion_time(
        record.get("date"), "history.date",
    )
    completion = record.get("completed_at")
    has_completion = completion is not None and completion != ""
    sequence = record.get("runtime_sequence")
    if sequence is not None and (type(sequence) is not int or sequence <= 0):
        _error("invalid_runtime_sequence", "runtime_sequence must be a positive transaction order")
    if (has_completion or sequence is not None) and record.get("status") != "completed":
        _error("completion_on_noncompleted_record", "Only completed participations can have completion metadata")
    if sequence is not None and not has_completion:
        _error("missing_runtime_completion", "Runtime context requires a completion date or timestamp")
    if not has_completion:
        return participation, participation, participation_order, False, None
    completion_day, order_key, has_time = _completion_time(completion, "completed_at")
    if sequence is not None:
        # Snapshot simulations and wall time deliberately have separate clocks.
        completion_day = _calendar_date(record.get("completed_on"), "completed_on")
        precedes = completion_day < participation
    else:
        precedes = (order_key < participation_order
                    if has_time and participation_has_time else completion_day < participation)
    if precedes:
        _error("completion_before_participation", "Completion precedes participation")
    return participation, completion_day, order_key, has_time, sequence


def _level(value, field, config):
    if type(value) is not int or not config.skill_min_level <= value <= config.skill_max_level:
        _error(
            "invalid_skill_level",
            "{} must be an integer between {} and {}".format(
                field, config.skill_min_level, config.skill_max_level
            ),
        )
    return value


def _event_index(events, config):
    index = {}
    for event in events:
        if not isinstance(event, Mapping):
            _error("invalid_event", "Each event must be a mapping")
        event_id = _identifier(event.get("event_id"), "event.event_id")
        if event_id in index:
            _error("duplicate_event_id", "Duplicate event_id: {}".format(event_id))
        if event.get("format") not in config.event_formats:
            _error("invalid_event_format", "Unknown format for {}".format(event_id))
        developments = event.get("develops_skills")
        if not isinstance(developments, (list, tuple)):
            _error("invalid_develops_skills", "{}.develops_skills must be a sequence".format(event_id))
        seen_skills = set()
        for development in developments:
            if not isinstance(development, Mapping):
                _error("invalid_develops_skills", "Each skill development must be a mapping")
            skill_id = _identifier(development.get("skill_id"), "development.skill_id")
            if skill_id in seen_skills:
                _error("duplicate_developed_skill", "{} repeats {}".format(event_id, skill_id))
            seen_skills.add(skill_id)
            gain = development.get("gain")
            if type(gain) is not int or gain < 0:
                _error("invalid_gain", "{}.{}.gain must be a nonnegative integer".format(event_id, skill_id))
            _level(development.get("max_level"), "{}.{}.max_level".format(event_id, skill_id), config)
        index[event_id] = event
    return index


def reconstruct_effective_skills(
    employee: Mapping,
    events: Sequence[Mapping],
    history: Sequence[Mapping],
    *,
    as_of: Union[str, date],
    config: RecommendationConfig = DEFAULT_CONFIG,
) -> SkillsReconstruction:
    """Return independent effective skills and auditable reconstruction evidence.

    Only identical repeated ``record_id`` values are deduplicated. Distinct
    participation IDs remain separate even for the same employee and event.
    Status controls completion; percentages and assessments never scale gains.
    Applied IDs include skill-bearing participations even when gains are capped;
    no-skill participations are excluded. Changes retain zero-gain evidence.
    The caller supplies already-validated dataset mappings. Guards here protect
    arithmetic, references and chronology rather than replace backend validation.
    """
    if not isinstance(employee, Mapping):
        _error("invalid_employee", "employee must be a mapping")
    _require_sequence(events, "events", "invalid_events")
    _require_sequence(history, "history", "invalid_history")
    employee_id = _identifier(employee.get("employee_id"), "employee.employee_id")
    snapshot = _calendar_date(as_of, "as_of")
    review = _calendar_date(employee.get("last_review_date"), "last_review_date")
    if review > snapshot:
        _error("review_after_snapshot", "last_review_date cannot be later than as_of")
    baseline = employee.get("skills")
    if not isinstance(baseline, Mapping):
        _error("invalid_skills", "employee.skills must be a mapping")
    effective = {}
    for skill_id, value in baseline.items():
        _identifier(skill_id, "employee.skills key")
        effective[skill_id] = _level(value, "employee.skills.{}".format(skill_id), config)
    event_index = _event_index(events, config)

    seen_records = {}
    replay = []
    runtime_sequences = set()
    uncertain_ids = []
    legacy_ids = []
    for record in history:
        if not isinstance(record, Mapping):
            _error("invalid_history", "Each history record must be a mapping")
        if record.get("employee_id") != employee_id:
            continue
        record_id = _identifier(record.get("record_id"), "history.record_id")
        if record_id in seen_records:
            if record != seen_records[record_id]:
                _error("conflicting_record_id", "Conflicting history record_id: {}".format(record_id))
            continue
        seen_records[record_id] = record
        status = record.get("status")
        if status not in config.history_statuses:
            _error("invalid_history_status", "Unknown status on {}".format(record_id))
        participation, effective_date, order_key, has_time, sequence = _participation_timing(record)
        completion = record.get("completed_at")
        has_completion = completion is not None and completion != ""
        if sequence is not None:
            if sequence in runtime_sequences:
                _error("duplicate_runtime_sequence", "Runtime transaction order must be unique")
            runtime_sequences.add(sequence)
        if status != "completed":
            continue
        event_id = _identifier(record.get("event_id"), "{}.event_id".format(record_id))
        if event_id not in event_index:
            _error("unknown_event", "{} references unknown event {}".format(record_id, event_id))
        event = event_index[event_id]
        if has_completion:
            date_basis = "runtime_completed_on" if sequence is not None else "completed_at"
        else:
            date_basis = "enrollment_date" if event["format"] == "self_paced" else "session_date"
        if effective_date > snapshot or not event["develops_skills"]:
            continue
        if effective_date < review or (effective_date == review and sequence is None):
            if not has_completion and event["format"] == "self_paced":
                uncertain_ids.append(record_id)
            continue
        if not has_completion:
            legacy_ids.append(record_id)
        replay.append((order_key, record_id, event, date_basis, effective_date, has_time, sequence))

    def replay_key(item):
        # A sort anchor is not a fabricated completion timestamp. Runtime
        # operations follow the loaded legacy snapshot on the same logical day;
        # transaction sequence remains authoritative even if the wall clock ties
        # or moves backwards. UTC ordering for every legacy row is unchanged.
        anchor = (datetime.combine(item[4], time.max, timezone.utc)
                  if item[6] is not None else item[0])
        return anchor, item[6] is not None, item[6] or 0, item[1]

    replay.sort(key=replay_key)
    skill_changes = []
    applied_ids = []
    for _, record_id, event, date_basis, _, _, _ in replay:
        applied_ids.append(record_id)
        for development in sorted(event["develops_skills"], key=lambda item: item["skill_id"]):
            skill_id = development["skill_id"]
            before = effective.get(skill_id, 0)
            gain_applied = min(development["gain"], max(0, development["max_level"] - before))
            after = before + gain_applied
            effective[skill_id] = after
            skill_changes.append({
                "record_id": record_id,
                "event_id": event["event_id"],
                "skill_id": skill_id,
                "before": before,
                "after": after,
                "gain_applied": gain_applied,
                "date_basis": date_basis,
            })

    # Compare possible UTC intervals, not stated dates: an offset timestamp can
    # fall inside another calendar date's UTC interval. Exact times are points;
    # date-only values occupy their UTC day. Disjoint skill gains commute.
    order_uncertain = set()
    for left_index, left in enumerate(replay):
        left_skills = {item["skill_id"] for item in left[2]["develops_skills"]}
        left_end = left[0] if left[5] else left[0].replace(hour=23, minute=59, second=59, microsecond=999999)
        for right in replay[left_index + 1:]:
            if left[6] is not None or right[6] is not None:
                # Runtime ordering is explicit in the adapter context.
                continue
            right_skills = {item["skill_id"] for item in right[2]["develops_skills"]}
            right_end = right[0] if right[5] else right[0].replace(hour=23, minute=59, second=59, microsecond=999999)
            intervals_overlap = max(left[0], right[0]) <= min(left_end, right_end)
            if intervals_overlap and left_skills & right_skills:
                order_uncertain.update((left[1], right[1]))

    warnings = []
    if uncertain_ids:
        warnings.append({
            "code": "ambiguous_self_paced_completion",
            "message": "Self-paced enrollments on or before review have unknown completion dates; no additional gains were applied.",
            "record_ids": sorted(uncertain_ids),
        })
    if legacy_ids:
        warnings.append({
            "code": "completion_date_proxy",
            "message": "Participation dates substitute for missing completion timestamps. Skills are an estimate, not guaranteed exact or a lower bound; actual completion order may differ.",
            "record_ids": sorted(legacy_ids),
        })
    if order_uncertain:
        warnings.append({
            "code": "ambiguous_completion_order",
            "message": "Overlapping skill gains have overlapping possible completion times in UTC; deterministic ordering may differ from actual completion order.",
            "record_ids": sorted(order_uncertain),
        })
    return {
        "effective_skills": dict(sorted(effective.items())),
        "applied_record_ids": applied_ids,
        "skill_changes": skill_changes,
        "uncertain_record_ids": sorted(uncertain_ids),
        "warnings": warnings,
        "date_policy": "participation_date_proxy",
        "is_estimate": bool(warnings),
    }
