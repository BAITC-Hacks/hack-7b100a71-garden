"""Imports are validated against the current complete snapshot in one transaction."""
from backend.data.loader import parse_upload
from backend.data.repository import DatasetRepository, dataset_counts
from backend.data.validation import DatasetValidationError, merge_dataset
from backend.errors import AppError


class DatasetService:
    def __init__(self, repository: DatasetRepository):
        self.repository = repository

    def validate(self, files, mode="append"):
        view = self.repository.view()
        try:
            patch = parse_upload(files)
            dataset = merge_dataset(view.export_dataset(), patch, mode)
        except DatasetValidationError as exc:
            return {"valid": False, "mode": mode, "counts": {},
                    "errors": exc.issues, "version": view.version}
        return {"valid": True, "mode": mode, "counts": dataset_counts(dataset),
                "errors": [], "version": view.version}

    def upload(self, files, mode="append"):
        try:
            patch = parse_upload(files)

            def operation(state):
                state.dataset = merge_dataset(state.dataset, patch, mode)
                if mode == "replace":
                    state.receipts.clear()
                    state.completed_record_ids.clear()
                return {"uploaded": True, "mode": mode,
                        "counts": dataset_counts(state.dataset), "version": state.version}

            return self.repository.mutate(operation)
        except DatasetValidationError as exc:
            raise AppError("invalid_dataset", "Dataset validation failed; no changes were applied",
                           422, exc.issues) from exc
