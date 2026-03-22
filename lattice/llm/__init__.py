"""lattice.llm — LLM integration for capability matching and generation."""

from lattice.llm.prompts import (
    GENERATE_SYSTEM_PROMPT,
    MATCH_SYSTEM_PROMPT,
    build_generate_prompt,
    build_match_prompt,
    get_generate_system_prompt,
)
from lattice.llm.provider import (
    AnthropicBackend,
    LLMBackend,
    LLMResponse,
    OpenAIBackend,
    get_llm_client,
)

__all__ = [
    "GENERATE_SYSTEM_PROMPT",
    "MATCH_SYSTEM_PROMPT",
    "AnthropicBackend",
    "LLMBackend",
    "LLMResponse",
    "OpenAIBackend",
    "build_generate_prompt",
    "build_match_prompt",
    "get_generate_system_prompt",
    "get_llm_client",
]
