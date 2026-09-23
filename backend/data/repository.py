"""Indexed, isolated reads and atomic single-process mutations.

The official files are read once. A separate runtime snapshot persists imports,
completed activities and idempotency receipts. Run one application worker.
"""
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
from typing import Any, Callable, Dict, Iterable, List, Optional, TypeVar

from backend.errors import AppError
from backend.models.domain import Dataset
from backend.data.validation import validate_dataset

T = TypeVar("T")


def dataset_counts(dataset: Dataset) -> Dict[str, int]:
    return {key: len(getattr(dataset, key)) for key in
            ("employees", "skills", "role_profiles", "events", "history")}


class RepositoryView:
    """A detached snapshot for one request or recommendation calculation."""

    def __init__(self, dataset: Dataset, version: int = 1,
                 completed_record_ids: Optional[Iterable[str]] = None):
        self._dataset = dataset.model_copy(deep=True)
        self.version = version
        self.as_of_date = self._dataset.meta.as_of_date
        self._live_completed_ids = tuple(completed_record_ids or ())
        self._employees = {item.employee_id: item for item in self._dataset.employees}
        self._skills = {item.skill_id: item for item in self._dataset.skills}
        self._profiles = {(item.role, item.grade): item for item in self._dataset.role_profiles}
        self._events = {item.event_id: item for item in self._dataset.events}
        self._history = {}
        for record in sorted(self._dataset.history, key=lambda item: (item.date, item.record_id)):
            self._history.setdefault(record.employee_id, []).append(record)
        self._skill_cache = {}

    @staticmethod
    def _copy(value):
        return value.model_copy(deep=True) if value is not None else None

    def export_dataset(self) -> Dataset:
        return self._dataset.model_copy(deep=True)

    def counts(self) -> Dict[str, int]:
        return dataset_counts(self._dataset)

    def get_employee(self, employee_id):
        return self._copy(self._employees.get(employee_id))

    def get_all_employees(self):
        return [self._copy(item) for item in self._dataset.employees]

    def get_skill(self, skill_id):
        return self._copy(self._skills.get(skill_id))

    def get_all_skills(self):
        return [self._copy(item) for item in self._dataset.skills]

    def get_role_profile(self, role, grade):
        return self._copy(self._profiles.get((role, grade)))

    def get_all_role_profiles(self):
        return [self._copy(item) for item in self._dataset.role_profiles]

    def get_event(self, event_id):
        return self._copy(self._events.get(event_id))

    def get_all_events(self):
        return [self._copy(item) for item in self._dataset.events]

    def get_employee_history(self, employee_id):
        return [self._copy(item) for item in self._history.get(employee_id, ())]

    def get_all_history(self):
        return [self._copy(item) for item in self._dataset.history]

    def get_runtime_completion_ids(self):
        """Return the trusted persisted operation order, detached from storage."""
        return tuple(self._live_completed_ids)

    def get_effective_skills(self, employee_id):
        if employee_id not in self._skill_cache:
            from backend.services.skill_projection import project_skills
            employee = self._employees.get(employee_id)
            if employee is None:
                raise AppError("employee_not_found", "Employee not found", 404)
            self._skill_cache[employee_id] = project_skills(
                employee, self._history.get(employee_id, ()), self._events,
                self._live_completed_ids, as_of=self.as_of_date,
            )
        return dict(self._skill_cache[employee_id])


@dataclass
class MutableState:
    dataset: Dataset
    version: int = 1
    receipts: Dict[str, dict] = field(default_factory=dict)
    completed_record_ids: List[str] = field(default_factory=list)
    dirty: bool = True

    def clone(self):
        return MutableState(
            self.dataset.model_copy(deep=True), self.version,
            json.loads(json.dumps(self.receipts)), list(self.completed_record_ids),
        )

    def view(self):
        return RepositoryView(self.dataset, self.version, self.completed_record_ids)


def validate_runtime_state(state: MutableState) -> MutableState:
    """Validate persisted domain data, completion order and original receipts.

    Both JSON recovery and relational reads use the same integrity contract.
    Replace the dataset with its validated copy only after all checks succeed.
    """
    dataset = validate_dataset(state.dataset)
    completed_ids = state.completed_record_ids
    if (not isinstance(completed_ids, list)
            or any(not isinstance(record_id, str) for record_id in completed_ids)
            or len(completed_ids) != len(set(completed_ids))):
        raise ValueError("runtime completion order is invalid")
    known_ids = {record.record_id for record in dataset.history if record.status == "completed"}
    if not set(completed_ids) <= known_ids:
        raise ValueError("runtime completion references are invalid")
    version = state.version
    receipts = state.receipts
    if type(version) is not int or version < 1 or not isinstance(receipts, dict):
        raise ValueError("invalid runtime state metadata")
    for key, receipt in receipts.items():
        if (not isinstance(key, str) or not isinstance(receipt, dict)
                or not isinstance(receipt.get("fingerprint"), str)
                or not isinstance(receipt.get("result"), dict)):
            raise ValueError("invalid idempotency receipt")
        result = receipt["result"]
        activity = result.get("activity")
        if (not isinstance(activity, dict) or activity.get("record_id") not in completed_ids
                or not isinstance(result.get("effective_skills"), dict)
                or not isinstance(result.get("skill_changes"), list)
                or type(result.get("version")) is not int
                or not 1 <= result["version"] <= version):
            raise ValueError("invalid idempotency result")
    state.dataset = dataset
    return state


class DatasetRepository:
    def __init__(self, dataset: Dataset, state_path: Optional[Path] = None):
        dataset = validate_dataset(dataset)
        self._lock = RLock()
        self._state_path = Path(state_path) if state_path is not None else None
        source = dataset.model_dump(mode="json")
        # Keep fingerprints of v1 state stable when new optional fields are
        # absent from the original input; do not discard supplied timestamps.
        for record in source["history"]:
            for field_name in ("completed_at", "runtime_sequence"):
                if record.get(field_name) is None:
                    record.pop(field_name, None)
        canonical = json.dumps(source, sort_keys=True,
                               separators=(",", ":"), ensure_ascii=False)
        self._source_fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
        self._state = MutableState(dataset.model_copy(deep=True))
        if self._state_path is not None and self._state_path.exists():
            self._restore()

    @classmethod
    def from_directory(cls, directory: Path, state_path: Optional[Path] = None):
        from backend.data.loader import load_dataset
        return cls(load_dataset(Path(directory)), state_path)

    @property
    def version(self):
        with self._lock:
            return self._state.version

    def view(self) -> RepositoryView:
        with self._lock:
            return self._state.view()

    def mutate(self, operation: Callable[[MutableState], T]) -> T:
        """Validate and persist before publishing; exceptions leave all state intact."""
        with self._lock:
            candidate = self._state.clone()
            candidate.version += 1
            result = operation(candidate)
            if not candidate.dirty:
                return result
            candidate.dataset = validate_dataset(candidate.dataset)
            self._persist(candidate)
            self._state = candidate
            return result

    def _persist(self, state: MutableState):
        if self._state_path is None:
            return
        temporary = None
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": 2,
                "source_fingerprint": self._source_fingerprint,
                "version": state.version,
                "dataset": state.dataset.model_dump(mode="json"),
                "receipts": state.receipts,
                "completed_record_ids": list(state.completed_record_ids),
            }
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False,
                                             dir=self._state_path.parent,
                                             prefix=".career-quest-", suffix=".tmp") as stream:
                temporary = Path(stream.name)
                json.dump(payload, stream, ensure_ascii=False, allow_nan=False,
                          separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self._state_path)
        except (OSError, ValueError) as exc:
            raise AppError("state_write_failed", "Could not persist runtime state; no changes were applied", 503) from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _restore(self):
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
            if payload.get("schema_version") not in {1, 2}:
                raise ValueError("unsupported runtime state schema")
            if payload.get("source_fingerprint") != self._source_fingerprint:
                raise ValueError("runtime state belongs to a different source dataset; use a separate state path")
            dataset = Dataset.model_validate(payload["dataset"])
            self._state = validate_runtime_state(MutableState(
                dataset, payload["version"], payload["receipts"], payload["completed_record_ids"],
            ))
        except Exception as exc:
            raise ValueError("Cannot restore runtime state: " + str(exc)) from exc

    # Convenience accessors preserve the same defensive-copy contract as views.
    def get_employee(self, employee_id):
        return self.view().get_employee(employee_id)

    def get_all_employees(self):
        return self.view().get_all_employees()

    def get_skill(self, skill_id):
        return self.view().get_skill(skill_id)

    def get_all_skills(self):
        return self.view().get_all_skills()

    def get_role_profile(self, role, grade):
        return self.view().get_role_profile(role, grade)

    def get_all_role_profiles(self):
        return self.view().get_all_role_profiles()

    def get_event(self, event_id):
        return self.view().get_event(event_id)

    def get_all_events(self):
        return self.view().get_all_events()

    def get_employee_history(self, employee_id):
        return self.view().get_employee_history(employee_id)

    def get_all_history(self):
        return self.view().get_all_history()

    def get_effective_skills(self, employee_id):
        return self.view().get_effective_skills(employee_id)
