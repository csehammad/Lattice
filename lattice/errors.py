"""Lattice exception hierarchy."""

from __future__ import annotations


class LatticeError(Exception):
    """Base exception for all Lattice errors."""


class AbortExecution(LatticeError):
    """Raised when a hard-failure policy exhausts retries and aborts the capability."""

    def __init__(self, step_name: str, cause: BaseException | None = None):
        self.step_name = step_name
        self.cause = cause
        super().__init__(f"Execution aborted at step '{step_name}': {cause}")


class StepFailure(LatticeError):
    """A step failed after exhausting its retry policy."""

    def __init__(self, step_name: str, cause: BaseException | None = None):
        self.step_name = step_name
        self.cause = cause
        super().__init__(f"Step '{step_name}' failed: {cause}")


class PermissionDenied(LatticeError):
    """The requesting identity lacks a required scope or role."""

    def __init__(self, step_name: str, required: str, available: set[str]):
        self.step_name = step_name
        self.required = required
        self.available = available
        super().__init__(
            f"Step '{step_name}' requires scope '{required}'; available scopes: {available}"
        )


class ValidationError(LatticeError):
    """Capability input or projection schema validation failed."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)
