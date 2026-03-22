"""@retry decorator — declares the retry policy for a step."""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from lattice.step import STEP_META_ATTR, StepMetadata


@dataclass
class RetryPolicy:
    max_attempts: int
    backoff: str  # "exponential", "linear", "fixed"
    on: tuple[type[BaseException], ...]
    base_delay: float = 1.0  # seconds

    def delay_for(self, attempt: int) -> float:
        if self.backoff == "exponential":
            return self.base_delay * (2**attempt) + random.uniform(0, 0.5)
        elif self.backoff == "linear":
            return self.base_delay * (attempt + 1)
        return self.base_delay


def retry(
    max: int = 3,
    backoff: str = "exponential",
    on: Sequence[type[BaseException]] | None = None,
    base_delay: float = 1.0,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Attach a retry policy to a @step function.

    Must be applied *after* @step so the StepMetadata already exists::

        @step(depends_on=[], scope="compliance.read")
        @retry(max=3, backoff="exponential", on=[TimeoutError])
        async def sanctions_check(): ...
    """
    policy = RetryPolicy(
        max_attempts=max,
        backoff=backoff,
        on=tuple(on or (Exception,)),
        base_delay=base_delay,
    )

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        meta: StepMetadata | None = getattr(fn, STEP_META_ATTR, None)
        if meta is not None:
            meta.retry_policy = policy
        else:
            # @retry applied before @step — stash it for @step to pick up
            fn._lattice_retry_policy = policy  # type: ignore[attr-defined]
        return fn

    return decorator
