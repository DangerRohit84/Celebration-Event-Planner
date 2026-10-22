"""LLM provider port (DIP). Implementations: echo, gemini, openai-compat."""

from __future__ import annotations

from typing import Protocol

from ..prompting import (
    CANNOT_DETERMINE,
    PLAIN_HEADER,
    STANDARD_HEADER,
    plain_sentence,
)

PLAIN_LANGUAGE_SYSTEM = (
    "You explain celebration and event planning in simple everyday language. "
    "Use short sentences, one idea per sentence, and no jargon."
)


class LLMProvider(Protocol):
    """Port for LLM providers (DIP)."""

    def answer(self, prompt: str, *, plain_language: bool = False) -> str:
        """Answer a prompt with the provider's model.

        Args:
            prompt: Fully rendered prompt text to answer.
            plain_language: When True, the answer must be written in short,
                jargon-free sentences. Implementations that call out to a
                remote model pass the flag into their system prompt.

        Returns:
            The generated answer text.
        """
        ...


class EchoProvider:
    """Deterministic offline baseline: returns a trimmed lead of the prompt context."""

    def answer(self, prompt: str, *, plain_language: bool = False) -> str:
        """Return a deterministic lead of the prompt context.

        In plain-language mode the entries are shortened, their bracketed
        source markers are dropped and the header is shorter, so the
        plain-language rendering is genuinely shorter than the standard one.

        Args:
            prompt: Prompt text whose bracketed context lines are extracted.
            plain_language: When True, render the ideas in a simpler form.

        Returns:
            The extracted ideas, or a "Cannot Determine" notice when the prompt
            carries no context lines.
        """
        # Extract context lines; return first few as a deterministic "idea".
        lines = [ln for ln in prompt.splitlines() if ln.strip()]
        ctx = [ln for ln in lines if ln.startswith("[")]
        if not ctx:
            return CANNOT_DETERMINE
        if plain_language:
            body = "\n".join(f"- {plain_sentence(c)}" for c in ctx[:5])
            return PLAIN_HEADER + "\n" + body
        return STANDARD_HEADER + "\n" + "\n".join(f"- {c}" for c in ctx[:5])
