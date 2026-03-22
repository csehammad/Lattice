"""Unified LLM client with OpenAI and Anthropic backends."""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Wrapper around the raw text returned by an LLM."""

    text: str

    def extract_json(self) -> Any:
        """Pull the first JSON object or array out of the response."""
        # Try the full text first
        try:
            return json.loads(self.text)
        except json.JSONDecodeError:
            pass
        # Look for a fenced ```json block
        m = re.search(r"```json\s*(.*?)```", self.text, re.DOTALL)
        if m:
            return json.loads(m.group(1).strip())
        # Look for any { ... } block
        m = re.search(r"\{.*\}", self.text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise ValueError(f"No JSON found in LLM response:\n{self.text[:500]}")

    def extract_python(self) -> str:
        """Pull the first Python code block out of the response."""
        m = re.search(r"```python\s*(.*?)```", self.text, re.DOTALL)
        if m:
            return m.group(1).strip()
        # If no fenced block, return the full text (the LLM may have
        # returned raw code without fences)
        return self.text.strip()


class LLMBackend(ABC):
    """Base class for LLM provider backends."""

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> LLMResponse: ...


class OpenAIBackend(LLMBackend):
    def __init__(self, model: str, api_key: str) -> None:
        self.model = model
        self.api_key = api_key

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> LLMResponse:
        try:
            import openai
        except ImportError:
            raise ImportError(
                "The openai package is required for the OpenAI backend. "
                "Install it with: pip install 'lattice[openai]'"
            ) from None
        client = openai.OpenAI(api_key=self.api_key)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        return LLMResponse(text=resp.choices[0].message.content or "")


class AnthropicBackend(LLMBackend):
    def __init__(self, model: str, api_key: str) -> None:
        self.model = model
        self.api_key = api_key

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> LLMResponse:
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "The anthropic package is required for the Anthropic backend. "
                "Install it with: pip install 'lattice[anthropic]'"
            ) from None
        client = anthropic.Anthropic(api_key=self.api_key)
        resp = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=temperature,
        )
        text_parts: list[str] = []
        for block in resp.content:
            block_text = getattr(block, "text", None)
            if isinstance(block_text, str):
                text_parts.append(block_text)
        return LLMResponse(text="\n".join(text_parts))


_DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-20250514",
}


def get_llm_client(
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> LLMBackend:
    """Build an LLM backend from explicit args, env vars, or defaults.

    Precedence (per parameter):
    1. Explicit argument
    2. Environment variable (LATTICE_LLM_PROVIDER, LATTICE_LLM_MODEL,
       OPENAI_API_KEY / ANTHROPIC_API_KEY)
    3. Default value
    """
    provider = provider or os.environ.get("LATTICE_LLM_PROVIDER", "openai")
    provider = provider.lower()

    if provider not in ("openai", "anthropic"):
        raise ValueError(f"Unsupported LLM provider: {provider!r}. Use 'openai' or 'anthropic'.")

    model = model or os.environ.get("LATTICE_LLM_MODEL") or _DEFAULT_MODELS[provider]

    if provider == "openai":
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY or pass --api-key.")
        return OpenAIBackend(model=model, api_key=api_key)

    # anthropic
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY or pass --api-key.")
    return AnthropicBackend(model=model, api_key=api_key)
