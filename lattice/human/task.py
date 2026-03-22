"""@human_task decorator — marks a step as requiring human execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lattice.step import STEP_META_ATTR, StepMetadata


def human_task(
    assigned_to: str = "unassigned",
    sla: str = "24_hours",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a step as a human task.

    The step function should call ``ctx.request_human_input()`` internally.
    This decorator attaches metadata so the runtime and CLI can report
    which steps are human vs automated.

    Usage::

        @step(depends_on=[], scope="compliance.read")
        @human_task(assigned_to="compliance_team", sla="4_hours")
        async def sanctions_check():
            return await ctx.request_human_input(...)
    """
    task_info = {"assigned_to": assigned_to, "sla": sla}

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        meta: StepMetadata | None = getattr(fn, STEP_META_ATTR, None)
        if meta is not None:
            meta.human_task = task_info
        else:
            fn._lattice_human_task = task_info  # type: ignore[attr-defined]
        return fn

    return decorator
