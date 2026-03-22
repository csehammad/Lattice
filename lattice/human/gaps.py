"""@needs_human_input decorator — marks a step as having implementation gaps."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from lattice.step import STEP_META_ATTR, StepMetadata


def needs_human_input(
    fields: Sequence[str] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a step as needing developer input before it can run.

    This is the "gap" marker for the semi-automated discovery path.
    The step's body is typically a placeholder (``pass`` or ``TODO``).

    Usage::

        @step(depends_on=[sanctions_check], scope="compliance.read")
        @needs_human_input(fields=["api_client", "field_mapping"])
        async def insurance_verification():
            pass
    """
    gap_fields = list(fields or [])

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        meta: StepMetadata | None = getattr(fn, STEP_META_ATTR, None)
        if meta is not None:
            meta.needs_human_input = gap_fields
        else:
            fn._lattice_needs_human_input = gap_fields  # type: ignore[attr-defined]
        return fn

    return decorator
