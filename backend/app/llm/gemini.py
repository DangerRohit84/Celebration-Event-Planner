"""Gemini provider (optional at runtime; falls back to echo)."""

from __future__ import annotations

from ..config import settings
from .base import PLAIN_LANGUAGE_SYSTEM


class GeminiProvider:
    """Gemini LLM provider."""

    def __init__(self) -> None:
        """Create the Gemini client from the configured API key and model.

        Raises:
            ImportError: When the ``google-genai`` package is not installed.
        """
        from google import genai  # type: ignore[import-untyped]

        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model

    def answer(self, prompt: str, *, plain_language: bool = False) -> str:
        """Generate an answer from the prompt.

        Args:
            prompt: Prompt text sent to the Gemini model.
            plain_language: When True, the plain-language system instruction
                is added to the request.

        Returns:
            The generated answer text, stripped of surrounding whitespace.
        """
        contents = prompt
        if plain_language:
            contents = f"{PLAIN_LANGUAGE_SYSTEM}\n\n{prompt}"
        resp = self._client.models.generate_content(model=self._model, contents=contents)
        return (resp.text or "").strip()
