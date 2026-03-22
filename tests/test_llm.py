"""Tests for lattice.llm — provider factory, prompts, response parsing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lattice.llm.prompts import (
    GENERATE_HUMAN_TASKS_ADDENDUM,
    GENERATE_SYSTEM_PROMPT,
    MATCH_SYSTEM_PROMPT,
    build_generate_prompt,
    build_match_prompt,
    get_generate_system_prompt,
)
from lattice.llm.provider import (
    AnthropicBackend,
    LLMResponse,
    OpenAIBackend,
    get_llm_client,
)

# -----------------------------------------------------------------------
# LLMResponse
# -----------------------------------------------------------------------


class TestLLMResponse:
    def test_extract_json_plain(self):
        resp = LLMResponse(text='{"capabilities": []}')
        assert resp.extract_json() == {"capabilities": []}

    def test_extract_json_fenced(self):
        resp = LLMResponse(text='Here is the result:\n```json\n{"a": 1}\n```\nDone.')
        assert resp.extract_json() == {"a": 1}

    def test_extract_json_embedded_object(self):
        resp = LLMResponse(text='Some text {"x": 2} more text')
        assert resp.extract_json() == {"x": 2}

    def test_extract_json_no_json(self):
        resp = LLMResponse(text="no json here")
        with pytest.raises(ValueError, match="No JSON found"):
            resp.extract_json()

    def test_extract_python_fenced(self):
        resp = LLMResponse(text='Here you go:\n```python\nprint("hello")\n```\nDone.')
        assert resp.extract_python() == 'print("hello")'

    def test_extract_python_raw(self):
        resp = LLMResponse(text='print("hello")')
        assert resp.extract_python() == 'print("hello")'


# -----------------------------------------------------------------------
# get_llm_client factory
# -----------------------------------------------------------------------


class TestGetLLMClient:
    def test_openai_from_args(self):
        client = get_llm_client(provider="openai", model="gpt-4o", api_key="sk-test")
        assert isinstance(client, OpenAIBackend)
        assert client.model == "gpt-4o"
        assert client.api_key == "sk-test"

    def test_anthropic_from_args(self):
        client = get_llm_client(
            provider="anthropic", model="claude-sonnet-4-20250514", api_key="ant-test"
        )
        assert isinstance(client, AnthropicBackend)
        assert client.model == "claude-sonnet-4-20250514"

    def test_openai_from_env(self, monkeypatch):
        monkeypatch.setenv("LATTICE_LLM_PROVIDER", "openai")
        monkeypatch.setenv("LATTICE_LLM_MODEL", "gpt-4-turbo")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        client = get_llm_client()
        assert isinstance(client, OpenAIBackend)
        assert client.model == "gpt-4-turbo"
        assert client.api_key == "sk-env"

    def test_anthropic_from_env(self, monkeypatch):
        monkeypatch.setenv("LATTICE_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-env")
        client = get_llm_client()
        assert isinstance(client, AnthropicBackend)

    def test_default_is_openai(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-default")
        monkeypatch.delenv("LATTICE_LLM_PROVIDER", raising=False)
        client = get_llm_client()
        assert isinstance(client, OpenAIBackend)
        assert client.model == "gpt-4o"

    def test_missing_api_key_openai(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="OpenAI API key required"):
            get_llm_client(provider="openai")

    def test_missing_api_key_anthropic(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ValueError, match="Anthropic API key required"):
            get_llm_client(provider="anthropic")

    def test_unsupported_provider(self):
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            get_llm_client(provider="gemini", api_key="x")


# -----------------------------------------------------------------------
# OpenAIBackend.complete (mocked)
# -----------------------------------------------------------------------


class TestOpenAIBackendComplete:
    def test_complete_calls_openai(self):
        backend = OpenAIBackend(model="gpt-4o", api_key="sk-test")

        mock_choice = MagicMock()
        mock_choice.message.content = '{"result": "ok"}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        mock_openai_mod = MagicMock()
        mock_openai_mod.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_mod}):
            resp = backend.complete("system", "user")

        assert resp.text == '{"result": "ok"}'
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ],
            temperature=0.2,
        )


# -----------------------------------------------------------------------
# AnthropicBackend.complete (mocked)
# -----------------------------------------------------------------------


class TestAnthropicBackendComplete:
    def test_complete_calls_anthropic(self):
        backend = AnthropicBackend(model="claude-sonnet-4-20250514", api_key="ant-test")

        mock_block = MagicMock()
        mock_block.text = '{"result": "ok"}'
        mock_response = MagicMock()
        mock_response.content = [mock_block]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        mock_anthropic_mod = MagicMock()
        mock_anthropic_mod.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_anthropic_mod}):
            resp = backend.complete("system", "user")

        assert resp.text == '{"result": "ok"}'
        mock_client.messages.create.assert_called_once_with(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system="system",
            messages=[{"role": "user", "content": "user"}],
            temperature=0.2,
        )


# -----------------------------------------------------------------------
# Prompts
# -----------------------------------------------------------------------


class TestPrompts:
    def test_match_system_prompt_is_nonempty(self):
        assert len(MATCH_SYSTEM_PROMPT) > 100
        assert "capability" in MATCH_SYSTEM_PROMPT.lower()

    def test_generate_system_prompt_is_nonempty(self):
        assert len(GENERATE_SYSTEM_PROMPT) > 100
        assert "@capability" in GENERATE_SYSTEM_PROMPT

    def test_build_match_prompt(self):
        ops = "- listUsers  GET /users\n- getUser  GET /users/{id}"
        prompt = build_match_prompt(ops, domain="hr")
        assert "listUsers" in prompt
        assert "hr" in prompt

    def test_build_match_prompt_no_domain(self):
        prompt = build_match_prompt("- op1  GET /x")
        assert "op1" in prompt
        assert "domain" not in prompt.lower().split("operations")[0]

    def test_build_generate_prompt(self):
        prompt = build_generate_prompt(
            "VendorOnboarding",
            "- checkSanctions  POST /sanctions",
            human_tasks=False,
        )
        assert "VendorOnboarding" in prompt
        assert "checkSanctions" in prompt
        assert "human" not in prompt.lower()

    def test_build_generate_prompt_human_tasks(self):
        prompt = build_generate_prompt("Cap", "- op1", human_tasks=True)
        assert "human" in prompt.lower()

    def test_get_generate_system_prompt_normal(self):
        sp = get_generate_system_prompt(human_tasks=False)
        assert "human_task" not in sp

    def test_get_generate_system_prompt_human(self):
        sp = get_generate_system_prompt(human_tasks=True)
        assert "human_task" in sp
        assert GENERATE_HUMAN_TASKS_ADDENDUM in sp


# -----------------------------------------------------------------------
# Inventory.to_llm_context
# -----------------------------------------------------------------------


class TestInventoryLLMContext:
    def test_to_llm_context(self):
        from lattice.discovery.inventory import Inventory
        from lattice.discovery.openapi import OperationInfo

        inv = Inventory()
        inv.add_operations(
            [
                OperationInfo(
                    operation_id="checkSanctions",
                    path="/sanctions/check",
                    method="POST",
                    summary="Check sanctions list",
                    parameters=[{"name": "entity_name"}, {"name": "country"}],
                    tags=["compliance"],
                ),
                OperationInfo(
                    operation_id="getVendor",
                    path="/vendors/{id}",
                    method="GET",
                    summary="Get vendor by ID",
                ),
            ]
        )

        ctx = inv.to_llm_context()
        assert "checkSanctions" in ctx
        assert "POST" in ctx
        assert "/sanctions/check" in ctx
        assert "entity_name" in ctx
        assert "compliance" in ctx
        assert "getVendor" in ctx
