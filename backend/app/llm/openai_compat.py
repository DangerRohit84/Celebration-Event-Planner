"""OpenAI-compatible provider."""

from __future__ import annotations

from ..config import settings


class OpenAICompatProvider:
    """OpenAI-compatible LLM provider."""

    def __init__(self):
        from openai import OpenAI  # type: ignore[import-untyped]

        self._client = OpenAI(
            api_key=settings.openai_api_key, base_url=settings.openai_base_url or None
        )
        self._model = settings.openai_model

    def answer(self, prompt: str) -> str:
        """Generate an answer from the prompt."""
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return (resp.choices[0].message.content or "").strip()
