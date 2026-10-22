"""LLM provider port (DIP). Implementations: echo, gemini, openai-compat."""

from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    """Port for LLM providers (DIP)."""

    def answer(self, prompt: str) -> str:
        """Answer a prompt with the provider's model.

        Args:
            prompt: Fully rendered prompt text to answer.

        Returns:
            The generated answer text.
        """
        ...


class EchoProvider:
    """Deterministic offline baseline: returns a trimmed lead of the prompt context."""

    def answer(self, prompt: str, *args, **kwargs) -> str:
        """Return a deterministic lead of the prompt context.

        Args:
            prompt: Prompt text whose bracketed context lines are extracted.
            *args: Ignored extra positional arguments, accepted for compatibility.
            **kwargs: Optional ``plain_language`` flag that selects a plain-language
                heading for the returned ideas.

        Returns:
            The extracted ideas, or a "Cannot Determine" notice when the prompt
            carries no context lines.
        """
        # Extract context lines; return first few as a deterministic "idea".
        lines = [ln for ln in prompt.splitlines() if ln.strip()]
        ctx = [ln for ln in lines if ln.startswith("[")]
        if not ctx:
            return "Cannot Determine from the provided context."
        if kwargs.get("plain_language"):
            return "Ideas (plain language):\n" + "\n".join(f"- {c}" for c in ctx[:5])
        return "Ideas:\n" + "\n".join(f"- {c}" for c in ctx[:5])
