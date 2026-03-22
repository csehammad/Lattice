"""@step decorator — declares a unit of work inside a capability.

Usage inside a @capability function body::

    @step(depends_on=[], scope="compliance.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @hard_failure(on_exhausted=abort)
    async def sanctions_check():
        ...

The decorator attaches metadata to the function.  The engine reads
that metadata at execution time to determine ordering and auth.

When an active step collector exists (set by the engine), the @step
decorator also registers the step there so the engine can discover
closures defined inside a capability body.
"""

from __future__ import annotations

import contextvars
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

STEP_META_ATTR = "_lattice_step"


@dataclass
class StepMetadata:
    name: str
    depends_on: list[str]
    scope: str | None
    fn: Callable[..., Any] | None = None
    retry_policy: Any | None = None
    soft_failure_fallback: Any | None = None
    hard_failure_action: Any | None = None
    human_task: dict[str, Any] | None = None
    needs_human_input: list[str] | None = None


# Context variable used by the engine to collect steps during
# the first call to a capability function.
_step_collector: contextvars.ContextVar[list[StepMetadata] | None] = contextvars.ContextVar(
    "lattice_step_collector", default=None
)


def _begin_collecting() -> tuple[list[StepMetadata], contextvars.Token[list[StepMetadata] | None]]:
    """Start collecting step definitions. Returns (collector_list, token)."""
    collector: list[StepMetadata] = []
    token = _step_collector.set(collector)
    return collector, token


def _end_collecting(token: contextvars.Token[list[StepMetadata] | None]) -> None:
    _step_collector.reset(token)


def step(
    depends_on: Sequence[Callable[..., Any]] | None = None,
    scope: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that marks an async function as a capability step."""

    dep_names: list[str] = []
    for dep in depends_on or []:
        if callable(dep):
            dep_names.append(dep.__name__)
        elif isinstance(dep, str):
            dep_names.append(dep)
        else:
            raise TypeError(f"depends_on entries must be functions or strings, got {type(dep)}")

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        meta = StepMetadata(
            name=fn.__name__,
            depends_on=dep_names,
            scope=scope,
            fn=fn,
        )

        # Pick up policies stashed by decorators that ran before @step
        # (since @step is the outermost decorator, inner decorators like
        # @retry, @soft_failure, @hard_failure run first and stash on fn)
        meta.retry_policy = getattr(fn, "_lattice_retry_policy", None)
        meta.soft_failure_fallback = getattr(fn, "_lattice_soft_failure", None)
        meta.hard_failure_action = getattr(fn, "_lattice_hard_failure", None)
        meta.human_task = getattr(fn, "_lattice_human_task", None)
        meta.needs_human_input = getattr(fn, "_lattice_needs_human_input", None)

        setattr(fn, STEP_META_ATTR, meta)

        # If an engine collection pass is active, register this step
        collector = _step_collector.get(None)
        if collector is not None:
            collector.append(meta)

        return fn

    return decorator


def get_step_meta(fn: Callable[..., Any]) -> StepMetadata | None:
    return getattr(fn, STEP_META_ATTR, None)
