"""Bearer identities and explicit access checks for the demo API."""

import secrets
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.errors import AppError


bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


@dataclass(frozen=True)
class Identity:
    role: str
    employee_id: Optional[str] = None


def _matches(provided: str, expected: str) -> bool:
    # Comparing UTF-8 bytes also handles non-ASCII input without raising a 500.
    return secrets.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def current_identity(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Identity:
    settings = request.app.state.settings
    if settings.auth_disabled:
        return Identity(role="hr")

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError("authentication_required", "A Bearer token is required.", status_code=401)
    token = credentials.credentials
    if not token or any(character.isspace() for character in token):
        raise AppError("invalid_token", "The Bearer token is invalid.", status_code=401)
    if not settings.hr_token and not settings.employee_tokens:
        raise AppError(
            "authentication_unavailable", "API authentication is not configured.", status_code=503
        )
    if settings.hr_token and _matches(token, settings.hr_token):
        return Identity(role="hr")

    employee_id = None
    for configured_token, configured_employee in settings.employee_tokens.items():
        if _matches(token, configured_token):
            employee_id = configured_employee
    if employee_id is not None:
        return Identity(role="employee", employee_id=employee_id)
    raise AppError("invalid_token", "The Bearer token is invalid.", status_code=401)


def require_hr(identity: Identity) -> None:
    if identity.role != "hr":
        raise AppError("forbidden", "HR access is required.", status_code=403)


def require_employee_or_hr(identity: Identity, employee_id: str) -> None:
    if identity.role == "hr":
        return
    if identity.role != "employee" or identity.employee_id != employee_id:
        raise AppError(
            "forbidden", "Employees can access only their own profile and activities.", status_code=403
        )


def current_hr_identity(identity: Identity = Depends(current_identity)) -> Identity:
    require_hr(identity)
    return identity
