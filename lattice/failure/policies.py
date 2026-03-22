"""Failure-mode decorators: @soft_failure, @hard_failure, and the abort sentinel."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from lattice.step import STEP_META_ATTR, StepMetadata


class _Abort:
    """Sentinel value used as ``on_exhausted=abort``."""

    def __repr__(self) -> str:
        return "abort"


abort = _Abort()


@dataclass
class SoftFailurePolicy:
    fallback: Any


@dataclass
class HardFailurePolicy:
    on_exhausted: Any  # typically ``abort``


def soft_failure(
    fallback: Any = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """If the step fails (after retries), return *fallback* instead of
    propagating the exception.  The capability continues."""

    policy = SoftFailurePolicy(fallback=fallback)

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        meta: StepMetadata | None = getattr(fn, STEP_META_ATTR, None)
        if meta is not None:
            meta.soft_failure_fallback = policy
        else:
            fn._lattice_soft_failure = policy  # type: ignore[attr-defined]
        return fn

    return decorator


def hard_failure(
    on_exhausted: Any = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """If the step fails (after retries), take the *on_exhausted* action.
    When ``on_exhausted=abort``, the entire capability is aborted."""

    policy = HardFailurePolicy(on_exhausted=on_exhausted)

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        meta: StepMetadata | None = getattr(fn, STEP_META_ATTR, None)
        if meta is not None:
            meta.hard_failure_action = policy
        else:
            fn._lattice_hard_failure = policy  # type: ignore[attr-defined]
        return fn

    return decorator
