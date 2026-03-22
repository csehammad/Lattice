"""Tests for agent input validation and session guardrails."""

from __future__ import annotations

import pytest

from demo.agent.agent import LatticeAgent
from lattice.runtime.engine import Engine
from lattice.runtime.registry import LazyRegistry


def _client_factory(name: str, credentials=None):
    raise KeyError(name)


def _build_agent() -> LatticeAgent:
    return LatticeAgent(
        lazy_registry=LazyRegistry({}),
        engine=Engine(),
        client_factory=_client_factory,
        max_messages=5,
    )


@pytest.mark.asyncio
async def test_search_tool_requires_non_empty_query():
    agent = _build_agent()
    result = await agent._handle_tool_call("search_capabilities", {"query": ""})
    assert result["error"]["code"] == "invalid_query"


@pytest.mark.asyncio
async def test_execute_tool_requires_capability_name():
    agent = _build_agent()
    result = await agent._handle_tool_call("execute_capability", {"inputs": {}})
    assert result["error"]["code"] == "missing_capability_name"


@pytest.mark.asyncio
async def test_execute_tool_requires_object_inputs():
    agent = _build_agent()
    result = await agent._handle_tool_call(
        "execute_capability",
        {"capability_name": "AnyCapability", "inputs": "bad"},
    )
    assert result["error"]["code"] == "invalid_inputs"


def test_message_history_is_bounded():
    agent = _build_agent()
    # keep system message + 4 latest entries
    agent._messages.extend(
        {"role": "user", "content": f"m{i}"} for i in range(10)
    )
    agent._prune_history()
    assert len(agent._messages) == 5
    assert agent._messages[0]["role"] == "system"
