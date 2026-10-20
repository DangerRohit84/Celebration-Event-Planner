"""Gemini provider (google-genai SDK). Optional at runtime; falls back to echo if unavailable."""
from __future__ import annotations

from ..config import settings


class GeminiProvider:
    def __init__(self):
        from google import genai
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model

    def answer(self, prompt: str) -> str:
        resp = self._client.models.generate_content(model=self._model, contents=prompt)
        return (resp.text or "").strip()
