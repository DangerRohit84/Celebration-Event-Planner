"""Factory for LLM providers (OCP: add new providers without editing callers)."""

from __future__ import annotations

from ..config import settings
from .base import EchoProvider, LLMProvider

EchoGroundedProvider = EchoProvider


def build_provider(provider: str | None = None) -> LLMProvider:
    """Build an LLM provider by name, falling back to echo on import/runtime errors."""
    name = (provider or settings.llm_provider).lower()
    if name == "gemini":
        try:
            from .gemini import GeminiProvider

            return GeminiProvider()
        except Exception:  # noqa: BLE001
            return EchoProvider()
    if name in ("openai", "openai-compat", "openai_compat"):
        try:
            from .openai_compat import OpenAICompatProvider

            return OpenAICompatProvider()
        except Exception:  # noqa: BLE001
            return EchoProvider()
    return EchoProvider()


def get_provider(name: str = "echo") -> LLMProvider:
    """Legal-style alias for build_provider."""
    # legal-style alias
    if name == "echo":
        return EchoProvider()
    return build_provider(name)
