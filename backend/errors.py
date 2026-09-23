"""Errors safe to expose through the public API."""
from typing import Any, List, Optional


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422,
                 details: Optional[List[Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []
