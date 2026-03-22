"""Runtime state container.

The engine populates a StateStore during execution.  Capability code
accesses it through the module-level ``state`` proxy so that
``state.sanctions_check.risk_score`` reads the return value of the
*sanctions_check* step.
"""

from __future__ import annotations

import contextvars
from typing import Any

from lattice.types import StepResult


class _StepView:
    """Attribute-access wrapper over a single step's result dict."""

    def __init__(self, step_name: str, data: StepResult) -> None:
        self._step_name = step_name
        self._data = data

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(
                f"Step '{self._step_name}' result has no field '{name}'. "
                f"Available: {list(self._data)}"
            ) from None

    def __repr__(self) -> str:
        return f"StepView({self._step_name}, {self._data!r})"


class StateStore:
    """Mutable store that accumulates step results for one execution."""

    def __init__(self) -> None:
        self._results: dict[str, StepResult] = {}

    def set(self, step_name: str, result: StepResult) -> None:
        self._results[step_name] = result

    def get(self, step_name: str) -> StepResult:
        return self._results[step_name]

    def has(self, step_name: str) -> bool:
        return step_name in self._results

    def view(self, step_name: str) -> _StepView:
        return _StepView(step_name, self._results[step_name])

    def all_results(self) -> dict[str, StepResult]:
        return dict(self._results)


# Per-execution context variable so concurrent runs don't collide.
_current_store: contextvars.ContextVar[StateStore | None] = contextvars.ContextVar(
    "lattice_state_store", default=None
)


class _StateProxy:
    """Module-level proxy that delegates attribute access to the
    active execution's StateStore.

    Capability code writes ``state.sanctions_check.risk_score``; the
    proxy looks up *sanctions_check* in the current store and returns
    a _StepView.
    """

    def __getattr__(self, step_name: str) -> _StepView:
        store = _current_store.get()
        if store is None:
            raise RuntimeError("state accessed outside of a capability execution")
        if not store.has(step_name):
            raise AttributeError(
                f"No result for step '{step_name}' — it either hasn't run yet or doesn't exist"
            )
        return store.view(step_name)


state = _StateProxy()


def bind_store(store: StateStore) -> contextvars.Token[StateStore | None]:
    """Bind *store* as the active state for the current execution."""
    return _current_store.set(store)


def unbind_store(token: contextvars.Token[StateStore | None]) -> None:
    """Restore previous state binding."""
    _current_store.reset(token)
