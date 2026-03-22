"""Scope and role checking, credential storage and injection."""

from __future__ import annotations

import contextvars
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from lattice.errors import PermissionDenied
from lattice.log import get_logger

logger = get_logger(__name__)


@dataclass
class CredentialStore:
    """Holds scopes, roles, and credentials available to the current execution.

    The runtime populates this before execution starts.  Each step's
    declared scope is checked against it.
    """

    granted_scopes: set[str] = field(default_factory=set)
    granted_roles: set[str] = field(default_factory=set)
    credentials: dict[str, Any] = field(default_factory=dict)

    def has_scope(self, scope: str) -> bool:
        if not scope:
            return True
        parts = scope.split(".")
        for i in range(len(parts)):
            prefix = ".".join(parts[: i + 1])
            if prefix in self.granted_scopes:
                return True
            if f"{prefix}.*" in self.granted_scopes:
                return True
        if "*" in self.granted_scopes:
            return True
        return scope in self.granted_scopes

    def has_role(self, role: str) -> bool:
        return role in self.granted_roles

    def check_scope(self, step_name: str, scope: str) -> None:
        if scope and not self.has_scope(scope):
            logger.warning(
                "Permission denied: step '%s' requires scope '%s' (available: %s)",
                step_name, scope, self.granted_scopes,
            )
            raise PermissionDenied(step_name, scope, self.granted_scopes)

    def check_role(self, step_name: str, role: str) -> None:
        if role and not self.has_role(role):
            logger.warning(
                "Permission denied: step '%s' requires role '%s'",
                step_name, role,
            )
            raise PermissionDenied(step_name, f"role:{role}", self.granted_scopes)

    def get_credential(self, name: str) -> Any:
        return self.credentials.get(name)


_current_creds: contextvars.ContextVar[CredentialStore | None] = contextvars.ContextVar(
    "lattice_credentials", default=None
)


def bind_credentials(store: CredentialStore) -> contextvars.Token[CredentialStore | None]:
    return _current_creds.set(store)


def unbind_credentials(token: contextvars.Token[CredentialStore | None]) -> None:
    _current_creds.reset(token)


def get_credentials() -> CredentialStore:
    store = _current_creds.get()
    if store is None:
        raise RuntimeError("No credential store bound for this execution")
    return store


def require_scope(scope: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Additional scope requirement decorator for a step."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        existing = getattr(fn, "_lattice_required_scopes", [])
        existing.append(scope)
        fn._lattice_required_scopes = existing  # type: ignore[attr-defined]
        return fn

    return decorator


def require_role(role: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Role requirement decorator for a step."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        existing = getattr(fn, "_lattice_required_roles", [])
        existing.append(role)
        fn._lattice_required_roles = existing  # type: ignore[attr-defined]
        return fn

    return decorator
