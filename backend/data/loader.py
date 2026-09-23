"""Read official UTF-8 JSON envelopes and CSV without altering their sources."""

import csv
import io
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from pydantic import ValidationError

from backend.data.validation import DatasetValidationError, schema_issues, validate_dataset
from backend.models.domain import (
    ActivityRecord, Dataset, DatasetMeta, EmployeesDocument, EventsDocument,
    SkillsDocument,
)


DOCUMENTS = {
    "employees.json": EmployeesDocument,
    "skills.json": SkillsDocument,
    "events.json": EventsDocument,
}
DATASET_FILENAMES = ("employees.json", "skills.json", "events.json", "activity_history.csv")
HISTORY_COLUMNS = (
    "record_id", "employee_id", "event_id", "date", "due_date", "status",
    "completion_pct", "score", "feedback_rating", "assigned_by",
)
OPTIONAL_HISTORY_COLUMNS = {"completed_on"}


def _issue(code: str, location: str, message: str) -> Dict[str, str]:
    return {"code": code, "location": location, "message": message}


def _decode(payload: bytes, filename: str, issues: List[Dict[str, str]]) -> Optional[str]:
    if not isinstance(payload, bytes):
        issues.append(_issue("invalid_file", filename, "File content must be bytes"))
        return None
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        issues.append(_issue("invalid_encoding", filename,
                             "Expected UTF-8 text; invalid byte at offset {}".format(exc.start)))
        return None


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Repeated JSON key: {}".format(key))
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("Non-finite JSON number: {}".format(value))


def _read_json(payload: bytes, filename: str, model, issues: List[Dict[str, str]]):
    text = _decode(payload, filename, issues)
    if text is None:
        return None
    try:
        content = json.loads(text, object_pairs_hook=_json_object, parse_constant=_invalid_constant)
    except json.JSONDecodeError as exc:
        issues.append(_issue("invalid_json", "{}:line {}:column {}".format(filename, exc.lineno, exc.colno),
                             exc.msg))
        return None
    except (ValueError, RecursionError) as exc:
        issues.append(_issue("invalid_json", filename, str(exc)))
        return None
    try:
        return model.model_validate(content)
    except ValidationError as exc:
        issues.extend(schema_issues(exc, filename))
        return None


def _read_history(payload: bytes, issues: List[Dict[str, str]]) -> List[ActivityRecord]:
    filename = "activity_history.csv"
    text = _decode(payload, filename, issues)
    if text is None:
        return []
    # newline="" leaves quoted CRLF/newline handling to the CSV parser.
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    records = []
    try:
        headers = reader.fieldnames
        if not headers:
            issues.append(_issue("missing_header", filename, "CSV requires a header row"))
            return []
        repeated = sorted({name for name in headers if headers.count(name) > 1})
        missing = sorted(set(HISTORY_COLUMNS) - set(headers))
        unknown = sorted(set(headers) - set(HISTORY_COLUMNS) - OPTIONAL_HISTORY_COLUMNS)
        if repeated:
            issues.append(_issue("duplicate_header", filename,
                                 "Repeated CSV columns: {}".format(", ".join(repeated))))
        if missing:
            issues.append(_issue("missing_header", filename,
                                 "Missing CSV columns: {}".format(", ".join(missing))))
        if unknown:
            issues.append(_issue("unknown_header", filename,
                                 "Unknown CSV columns: {}".format(", ".join(unknown))))
        if repeated or missing or unknown:
            return []
        for raw in reader:
            location = "{}:line {}".format(filename, reader.line_num)
            if None in raw or any(value is None for value in raw.values()):
                issues.append(_issue("invalid_csv_row", location,
                                     "Row must contain exactly one value for every header column"))
                continue
            row: Dict[str, Any] = {key: value.strip() for key, value in raw.items()}
            for name in ("due_date", "score", "feedback_rating", "completed_on"):
                if name in row and row[name] == "":
                    row[name] = None
            for name in ("completion_pct", "score", "feedback_rating"):
                value = row.get(name)
                if isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value):
                    try:
                        row[name] = int(value)
                    except ValueError:
                        # Oversized integer strings may exceed Python's digit
                        # limit; keep the text so normal schema errors handle it.
                        pass
            try:
                records.append(ActivityRecord.model_validate(row))
            except ValidationError as exc:
                issues.extend(schema_issues(exc, location))
    except csv.Error as exc:
        issues.append(_issue("invalid_csv", "{}:line {}".format(filename, reader.line_num), str(exc)))
    return records


def parse_upload(files: Mapping[str, bytes]) -> Dict[str, Any]:
    """Parse any selection of official documents into a typed partial snapshot.

    Cross-file metadata is checked here, while foreign keys are validated after
    merging with the active snapshot. CSV can therefore reference employees that
    already exist without requiring their profiles in the same upload.
    """
    issues: List[Dict[str, str]] = []
    patch: Dict[str, Any] = {}
    if not files:
        raise DatasetValidationError([_issue("empty_upload", "files", "At least one dataset file is required")])
    unknown = set(files) - set(DATASET_FILENAMES)
    for filename in sorted(unknown):
        issues.append(_issue("unknown_file", filename, "Expected an official JSON or activity_history.csv filename"))
    metadata: Optional[DatasetMeta] = None
    metadata_source = ""
    for filename, model in DOCUMENTS.items():
        if filename not in files:
            continue
        document = _read_json(files[filename], filename, model, issues)
        if document is None:
            continue
        if metadata is None:
            metadata = document.meta
            metadata_source = filename
        elif metadata != document.meta:
            issues.append(_issue("metadata_mismatch", filename + ".meta",
                                 "Dataset name, version and snapshot date must match {}".format(metadata_source)))
        for key in document.__class__.model_fields:
            if key != "meta":
                patch[key] = getattr(document, key)
    if metadata is not None:
        patch["meta"] = metadata
    if "activity_history.csv" in files:
        patch["history"] = _read_history(files["activity_history.csv"], issues)
    if issues:
        raise DatasetValidationError(issues)
    return patch


def load_dataset(path: Path) -> Dataset:
    """Load and validate all four official files from a dataset directory."""
    path = Path(path)
    files: Dict[str, bytes] = {}
    issues: List[Dict[str, str]] = []
    for filename in DATASET_FILENAMES:
        source = path / filename
        try:
            files[filename] = source.read_bytes()
        except OSError as exc:
            issues.append(_issue("file_read_error", str(source), str(exc)))
    if issues:
        raise DatasetValidationError(issues)
    return validate_dataset(parse_upload(files))
