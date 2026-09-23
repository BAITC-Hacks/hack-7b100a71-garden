"""Translate validated backend history into the independent engine boundary.

``completed_on`` is the logical snapshot date, while ``completed_at`` is the
actual recorded UTC instant. Never manufacture an instant for legacy state.
Only the repository's trusted operation order supplies runtime context.
"""
from copy import deepcopy


def history_for_engine(records, runtime_record_ids=()):
    order = {record_id: index + 1 for index, record_id in enumerate(runtime_record_ids)}
    result = []
    for record in records:
        row = record.model_dump(mode="json") if hasattr(record, "model_dump") else deepcopy(dict(record))
        record_id = row.get("record_id")
        if record_id in order:
            if row.get("runtime_sequence") is None:
                row["runtime_sequence"] = order[record_id]
        elif row.get("runtime_sequence") is not None:
            raise ValueError("Runtime sequence requires a trusted repository completion record")
        if row.get("completed_at") is None and row.get("completed_on") is not None:
            # A calendar date is intentionally still date-only evidence.
            row["completed_at"] = row["completed_on"]
        result.append(row)
    return result
