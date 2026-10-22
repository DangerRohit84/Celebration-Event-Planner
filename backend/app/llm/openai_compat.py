"""OpenAI-compatible provider."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..config import settings
from .base import PLAIN_LANGUAGE_SYSTEM

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam


class OpenAICompatProvider:
    """OpenAI-compatible LLM provider."""

    def __init__(self) -> None:
        """Create the OpenAI-compatible client from the configured credentials.

        Raises:
            ImportError: When the ``openai`` package is not installed.
        """
        from openai import OpenAI  # type: ignore[import-untyped]

        self._client = OpenAI(
            api_key=settings.openai_api_key, base_url=settings.openai_base_url or None
        )
        self._model = settings.openai_model

    def answer(self, prompt: str, *, plain_language: bool = False) -> str:
        """Generate an answer from the prompt.

        Args:
            prompt: Prompt text sent as the single user message.
            plain_language: When True, a plain-language system message is
                added ahead of the user message.

        Returns:
            The generated answer text, stripped of surrounding whitespace.
        """
        messages: list[ChatCompletionMessageParam] = []
        if plain_language:
            messages.append({"role": "system", "content": PLAIN_LANGUAGE_SYSTEM})
        messages.append({"role": "user", "content": prompt})
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0,
        )
        return (resp.choices[0].message.content or "").strip()
