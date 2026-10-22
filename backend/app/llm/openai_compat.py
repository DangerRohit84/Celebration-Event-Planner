"""OpenAI-compatible provider."""

from __future__ import annotations

from ..config import settings


class OpenAICompatProvider:
    """OpenAI-compatible LLM provider."""

    def __init__(self):
        """Create the OpenAI-compatible client from the configured credentials.

        Raises:
            ImportError: When the ``openai`` package is not installed.
        """
        from openai import OpenAI  # type: ignore[import-untyped]

        self._client = OpenAI(
            api_key=settings.openai_api_key, base_url=settings.openai_base_url or None
        )
        self._model = settings.openai_model

    def answer(self, prompt: str) -> str:
        """Generate an answer from the prompt.

        Args:
            prompt: Prompt text sent as the single user message.

        Returns:
            The generated answer text, stripped of surrounding whitespace.
        """
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return (resp.choices[0].message.content or "").strip()
