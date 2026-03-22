"""ExecutionContext — the ``ctx`` object passed to every capability."""

from __future__ import annotations

from typing import Any

from lattice.auth.scopes import CredentialStore
from lattice.intent import Intent
from lattice.log import get_logger

logger = get_logger(__name__)


class _ClientProxy:
    """Placeholder client returned by ``ctx.client(name)``.

    Callers can configure a *client_factory* on the ExecutionContext
    to return real API clients keyed by name.  Without a factory this
    proxy records calls for testing/auditing.
    """

    def __init__(self, name: str, credentials: CredentialStore | None = None) -> None:
        self.name = name
        self._credentials = credentials

    def __repr__(self) -> str:
        return f"Client({self.name!r})"

    def __getattr__(self, method: str) -> Any:
        async def _call(**kwargs: Any) -> Any:
            raise NotImplementedError(
                f"Client '{self.name}' has no real backend bound.  Called .{method}({kwargs})"
            )

        return _call


class ExecutionContext:
    """Passed as the first argument to a @capability function.

    Provides:
    - ``ctx.intent``  — the typed input fields
    - ``ctx.client(name)`` — obtain a backend client
    - ``ctx.request_human_input(task, expected_output)`` — request human input
    """

    def __init__(
        self,
        intent: Intent,
        credentials: CredentialStore | None = None,
        client_factory: Any | None = None,
        human_input_handler: Any | None = None,
        requester: str | None = None,
    ) -> None:
        self.intent = intent
        self._credentials = credentials
        self._client_factory = client_factory
        self._human_input_handler = human_input_handler
        self.requester = requester or "unknown"

    def client(self, name: str) -> Any:
        """Return a backend client for *name*.

        If a *client_factory* was provided, it is called with
        ``(name, credentials)``.  Otherwise returns a _ClientProxy.
        """
        if self._client_factory is not None:
            logger.debug("Resolving client '%s' via factory", name)
            return self._client_factory(name, self._credentials)
        logger.debug("No client factory; returning proxy for '%s'", name)
        return _ClientProxy(name, self._credentials)

    async def request_human_input(
        self,
        task: str,
        expected_output: dict[str, type] | None = None,
    ) -> dict[str, Any]:
        """Request input from a human operator.

        If a *human_input_handler* was provided, delegates to it.
        Otherwise raises NotImplementedError.
        """
        if self._human_input_handler is not None:
            return await self._human_input_handler(task, expected_output)
        raise NotImplementedError(f"No human input handler configured.  Task: {task}")
