"""LatticeAgent -- OpenAI function-calling agent backed by Lattice runtime.

Search-then-Execute pattern:

The model gets exactly TWO tools — ``search_capabilities`` and
``execute_capability``.  No capabilities are loaded upfront.  The model
first discovers what's available, then executes.  Lattice handles the
multi-step orchestration internally.

Flow:
  User: "Onboard Acme Corp as a supplier in the US"
    -> Model calls search_capabilities("vendor onboarding supplier")
    -> Returns matching capability signatures with input/output schemas
    -> Model calls execute_capability("VendorOnboarding", {vendor_name: ...})
    -> Lattice engine runs all steps, returns the projection
    -> Model responds in natural language
"""

from __future__ import annotations

import json
from typing import Any

from lattice.auth.scopes import CredentialStore
from lattice.runtime.engine import Engine
from lattice.runtime.registry import LazyRegistry


_ALL_DEMO_SCOPES = {
    "compliance.read",
    "vendor.write",
    "budget.read",
    "budget.write",
    "vendor.read",
    "approval.read",
    "approval.write",
    "travel.read",
    "travel.approve",
    "travel.book",
}

_SYSTEM_PROMPT = (
    "You are a helpful enterprise assistant powered by Lattice.\n\n"
    "You have TWO tools:\n"
    "1. search_capabilities — search for available capabilities by describing "
    "what you want to accomplish. ALWAYS call this first.\n"
    "2. execute_capability — execute a capability by its exact name with the "
    "required inputs. Only call this AFTER you know the capability name and "
    "its required inputs from a search.\n\n"
    "Workflow:\n"
    "- When the user asks you to do something, FIRST search for relevant "
    "capabilities.\n"
    "- Review the search results to find the best match and understand its "
    "required inputs.\n"
    "- Extract the input values from the user's message.\n"
    "- Execute the capability with the correct name and inputs.\n"
    "- After receiving the result (projection), explain what happened in "
    "clear, natural language. Include specific values (IDs, statuses, "
    "amounts). Do not make up information beyond what the projection "
    "contains."
)


class LatticeAgent:
    """An agent that discovers and executes Lattice capabilities via OpenAI.

    Uses the Search-then-Execute pattern: the model sees two meta-tools
    instead of N capability-specific tools.
    """

    def __init__(
        self,
        lazy_registry: LazyRegistry,
        engine: Engine,
        client_factory: Any,
        openai_model: str = "gpt-4o",
        scopes: set[str] | None = None,
        max_messages: int | None = 80,
    ) -> None:
        self.lazy_registry = lazy_registry
        self.engine = engine
        self.client_factory = client_factory
        self.openai_model = openai_model
        self.scopes = scopes or _ALL_DEMO_SCOPES
        self.max_messages = max_messages
        self._tools = LazyRegistry.openai_meta_tools()
        self._messages: list[dict[str, Any]] = [
            {"role": "system", "content": _SYSTEM_PROMPT}
        ]

    def _get_openai_client(self):
        import openai
        return openai.OpenAI()

    async def handle_message(self, user_message: str) -> str:
        """Process a user message through the search-then-execute loop."""
        self._messages.append({"role": "user", "content": user_message})
        self._prune_history()

        client = self._get_openai_client()

        # The model may need multiple rounds (search -> execute)
        for _ in range(5):
            response = client.chat.completions.create(
                model=self.openai_model,
                messages=self._messages,
                tools=self._tools,
                tool_choice="auto",
            )

            message = response.choices[0].message

            if not message.tool_calls:
                reply = message.content or ""
                self._messages.append({"role": "assistant", "content": reply})
                self._prune_history()
                return reply

            self._messages.append(message.model_dump())
            self._prune_history()

            for tool_call in message.tool_calls:
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError as exc:
                    result = self._tool_error(
                        code="invalid_tool_arguments",
                        message="Tool arguments are not valid JSON.",
                        details={"tool": tool_call.function.name, "error": str(exc)},
                    )
                else:
                    result = await self._handle_tool_call(
                        tool_call.function.name,
                        arguments if isinstance(arguments, dict) else {},
                    )
                self._messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, default=str),
                })
                self._prune_history()

        # Fallback if the model didn't produce a text response after max rounds
        final = client.chat.completions.create(
            model=self.openai_model,
            messages=self._messages,
        )
        reply = final.choices[0].message.content or ""
        self._messages.append({"role": "assistant", "content": reply})
        self._prune_history()
        return reply

    def _prune_history(self) -> None:
        """Bound session history to avoid unbounded growth."""
        if self.max_messages is None or self.max_messages <= 0:
            return
        if len(self._messages) <= self.max_messages:
            return
        system_msg = self._messages[0]
        tail = self._messages[-(self.max_messages - 1):]
        self._messages = [system_msg, *tail]

    @staticmethod
    def _tool_error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        }

    async def _handle_tool_call(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> Any:
        """Route a tool call to the appropriate handler."""
        if tool_name == "search_capabilities":
            query = arguments.get("query", "")
            if not isinstance(query, str) or not query.strip():
                return self._tool_error(
                    code="invalid_query",
                    message="search_capabilities requires a non-empty string query.",
                    details={"received": query},
                )
            return self._handle_search(query)
        elif tool_name == "execute_capability":
            cap_name = arguments.get("capability_name", "")
            inputs = arguments.get("inputs")
            if inputs is None:
                # Model may flatten inputs as top-level keys
                inputs = {k: v for k, v in arguments.items() if k != "capability_name"}
            if not isinstance(cap_name, str) or not cap_name.strip():
                return self._tool_error(
                    code="missing_capability_name",
                    message="execute_capability requires a non-empty capability_name.",
                    details={"received": cap_name},
                )
            if not isinstance(inputs, dict):
                return self._tool_error(
                    code="invalid_inputs",
                    message="execute_capability requires inputs to be an object.",
                    details={"received_type": type(inputs).__name__},
                )
            return await self._handle_execute(cap_name, inputs)
        else:
            return self._tool_error(
                code="unknown_tool",
                message=f"Unknown tool: {tool_name}",
            )

    def _handle_search(self, query: str) -> list[dict[str, Any]]:
        """Search the manifest and return matching capability metadata."""
        results = self.lazy_registry.search(query)
        if not results:
            return [{"message": "No capabilities found matching your query."}]
        return results

    async def _handle_execute(
        self, capability_name: str, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Load (if needed) and execute a capability through the engine."""
        self.lazy_registry.ensure_loaded(capability_name)
        fn = self.lazy_registry.get_function(capability_name)
        creds = CredentialStore(granted_scopes=self.scopes)

        result = await self.engine.execute(
            fn,
            inputs,
            credentials=creds,
            client_factory=self.client_factory,
            requester="lattice-agent",
        )
        return result

    @property
    def last_audit(self):
        if self.engine.audit_trail.records:
            return self.engine.audit_trail.records[-1]
        return None
