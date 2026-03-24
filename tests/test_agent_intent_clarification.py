"""Tests for unclear or incomplete user/tool payloads: clarification responses (not crashes).

These mirror how a model might call ``search_capabilities`` / ``execute_capability`` with
bad or partial data; the agent should return structured errors the model can turn into
questions for the user.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from demo.agent.agent import LatticeAgent
from demo.stubs import client_factory
from lattice.runtime.engine import Engine
from lattice.runtime.registry import LazyRegistry

_MANIFEST = Path(__file__).resolve().parent.parent / "demo" / "agent" / "registry.json"


def _agent(*, scopes: set[str] | None = None) -> LatticeAgent:
    return LatticeAgent(
        lazy_registry=LazyRegistry.from_manifest(_MANIFEST),
        engine=Engine(),
        client_factory=client_factory,
        scopes=scopes,
    )


# ---------------------------------------------------------------------------
# Planned scenarios (see test names below):
# 1. Search returns no capabilities → single-item list with a guidance message.
# 2. execute_capability with {} inputs → error + required_inputs from manifest + instruction.
# 3. Unknown capability name (with non-empty inputs) → error + instruction to search again.
# 4. Partial inputs (missing required fields) → ValidationError text + full schema hint.
# 5. Wrong Python type for a field → type mismatch text + schema hint.
# 6. Valid inputs but missing OAuth scopes → PermissionDenied text + scope instruction.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_no_matches_returns_guidance_message() -> None:
    agent = _agent()
    result = await agent._handle_tool_call("search_capabilities", {"query": "zzzzzzzz"})
    assert result == [{"message": "No capabilities found matching your query."}]


@pytest.mark.asyncio
async def test_execute_empty_inputs_returns_manifest_schema_and_instruction() -> None:
    agent = _agent()
    result = await agent._handle_tool_call(
        "execute_capability",
        {"capability_name": "VendorOnboarding", "inputs": {}},
    )
    assert result["error"].startswith("Missing inputs")
    assert result["required_inputs"] == {
        "vendor_name": "str",
        "vendor_type": "str",
        "region": "str",
    }
    assert "instruction" in result
    assert "inputs" in result["instruction"].lower()


@pytest.mark.asyncio
async def test_execute_unknown_capability_returns_error_and_search_instruction() -> None:
    agent = _agent()
    result = await agent._handle_tool_call(
        "execute_capability",
        {
            "capability_name": "NotInManifest",
            "inputs": {"vendor_name": "x", "vendor_type": "y", "region": "z"},
        },
    )
    assert "not in manifest" in result["error"].lower()
    assert "search_capabilities" in result["instruction"]


@pytest.mark.asyncio
async def test_execute_partial_inputs_returns_validation_error_and_schema() -> None:
    agent = _agent()
    result = await agent._handle_tool_call(
        "execute_capability",
        {
            "capability_name": "VendorOnboarding",
            "inputs": {"vendor_name": "Acme Corp"},
        },
    )
    assert "error" in result
    assert "Missing required input" in result["error"]
    assert result["required_inputs"] == {
        "vendor_name": "str",
        "vendor_type": "str",
        "region": "str",
    }
    assert "execute_capability" in result["instruction"]


@pytest.mark.asyncio
async def test_execute_wrong_input_type_returns_validation_error_and_schema() -> None:
    agent = _agent()
    result = await agent._handle_tool_call(
        "execute_capability",
        {
            "capability_name": "EquipmentProcurement",
            "inputs": {
                "item": "monitors",
                "quantity": "ten",
                "budget_department": "marketing",
                "preferred_vendor": "Acme Industrial Supply",
                "requested_by": "alice@company.com",
            },
        },
    )
    assert "quantity" in result["error"]
    assert "int" in result["error"].lower()
    assert result["required_inputs"]["quantity"] == "int"
    assert "instruction" in result


@pytest.mark.asyncio
async def test_execute_without_granted_scopes_returns_permission_denied_guidance() -> None:
    agent = _agent(scopes=set())
    result = await agent._handle_tool_call(
        "execute_capability",
        {
            "capability_name": "VendorOnboarding",
            "inputs": {
                "vendor_name": "Acme Corp",
                "vendor_type": "supplier",
                "region": "US",
            },
        },
    )
    assert "scope" in result["error"].lower()
    assert "required_inputs" in result
    assert "OAuth scopes" in result["instruction"] or "scopes" in result["instruction"].lower()
