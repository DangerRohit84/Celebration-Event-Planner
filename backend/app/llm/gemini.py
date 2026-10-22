"""Gemini provider (optional at runtime; falls back to echo)."""

from __future__ import annotations

from ..config import settings


class GeminiProvider:
    """Gemini LLM provider."""

    def __init__(self):
        from google import genai  # type: ignore[import-untyped]

        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model

    def answer(self, prompt: str) -> str:
        """Generate an answer from the prompt."""
        resp = self._client.models.generate_content(model=self._model, contents=prompt)
        return (resp.text or "").strip()
