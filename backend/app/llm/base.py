"""LLM provider port (DIP). Implementations: echo, gemini, openai-compat."""
from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    def answer(self, prompt: str) -> str: ...


class EchoProvider:
    """Deterministic offline baseline: returns a trimmed lead of the prompt context."""

    def answer(self, prompt: str, *args, **kwargs) -> str:
        # Extract context lines; return first few as a deterministic "idea".
        lines = [ln for ln in prompt.splitlines() if ln.strip()]
        ctx = [ln for ln in lines if ln.startswith("[")]
        if not ctx:
            return "Cannot Determine from the provided context."
        if kwargs.get("plain_language"):
            return "Ideas (plain language):\n" + "\n".join(f"- {c}" for c in ctx[:5])
        return "Ideas:\n" + "\n".join(f"- {c}" for c in ctx[:5])
