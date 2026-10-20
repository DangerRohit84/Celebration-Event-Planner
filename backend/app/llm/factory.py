"""Factory for LLM providers (OCP: add new providers without editing callers)."""
from __future__ import annotations

from .base import LLMProvider, EchoProvider
from ..config import settings

EchoGroundedProvider = EchoProvider


def build_provider(provider: str = None) -> LLMProvider:
    name = (provider or settings.llm_provider).lower()
    if name == "gemini":
        try:
            from .gemini import GeminiProvider
            return GeminiProvider()
        except Exception:
            return EchoProvider()
    if name in ("openai", "openai-compat", "openai_compat"):
        try:
            from .openai_compat import OpenAICompatProvider
            return OpenAICompatProvider()
        except Exception:
            return EchoProvider()
    return EchoProvider()


def get_provider(name: str = "echo") -> LLMProvider:
    # legal-style alias
    if name == "echo":
        return EchoProvider()
    return build_provider(name)
