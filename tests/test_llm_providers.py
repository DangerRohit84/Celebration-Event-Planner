"""LLM provider tests.

The docs claim that the grounded prompt is generated with "temperature 0".
That claim has to hold for every provider that can be selected with
``LLM_PROVIDER``, so the generation config of each one is inspected here
with a fake client - no network call is ever made.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.app.llm.base import PLAIN_LANGUAGE_SYSTEM
from backend.app.llm.gemini import GeminiProvider
from backend.app.llm.openai_compat import OpenAICompatProvider


class _FakeGeminiModels:
    """Records the arguments of a ``generate_content`` call."""

    def __init__(self, calls: list[dict]) -> None:
        """Store the list the calls are recorded into.

        Args:
            calls: The list that receives every recorded call.
        """
        self._calls = calls

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        """Record the call and return a canned response.

        Args:
            kwargs: The keyword arguments the provider passed.

        Returns:
            A response object carrying the canned answer text.
        """
        self._calls.append(dict(kwargs))
        return SimpleNamespace(text="  grounded answer  ")


class _FakeGeminiClient:
    """A stand-in for ``google.genai.Client``."""

    def __init__(self, calls: list[dict]) -> None:
        """Create the client with the list the calls are recorded into.

        Args:
            calls: The list that receives every recorded call.
        """
        self.models = _FakeGeminiModels(calls)


class _FakeOpenAIMessages:
    """Records the arguments of a ``chat.completions.create`` call."""

    def __init__(self, calls: list[dict]) -> None:
        """Store the list the calls are recorded into.

        Args:
            calls: The list that receives every recorded call.
        """
        self._calls = calls

    def create(self, **kwargs: object) -> SimpleNamespace:
        """Record the call and return a canned response.

        Args:
            kwargs: The keyword arguments the provider passed.

        Returns:
            A response object carrying the canned answer text.
        """
        self._calls.append(dict(kwargs))
        message = SimpleNamespace(content="  grounded answer  ")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _FakeOpenAIClient:
    """A stand-in for the ``openai.OpenAI`` client."""

    def __init__(self, calls: list[dict]) -> None:
        """Create the client with the list the calls are recorded into.

        Args:
            calls: The list that receives every recorded call.
        """
        self.chat = SimpleNamespace(completions=_FakeOpenAIMessages(calls))


def _gemini_provider(calls: list[dict]) -> GeminiProvider:
    """Build a Gemini provider backed by a fake client.

    Args:
        calls: The list that receives every recorded call.

    Returns:
        A provider whose client records instead of calling the API.
    """
    genai = pytest.importorskip("google.genai")
    original = genai.Client
    genai.Client = lambda **_kwargs: _FakeGeminiClient(calls)  # type: ignore[misc]
    try:
        return GeminiProvider()
    finally:
        genai.Client = original  # type: ignore[misc]


def _openai_provider(calls: list[dict]) -> OpenAICompatProvider:
    """Build an OpenAI-compatible provider backed by a fake client.

    Args:
        calls: The list that receives every recorded call.

    Returns:
        A provider whose client records instead of calling the API.
    """
    openai = pytest.importorskip("openai")
    original = openai.OpenAI
    openai.OpenAI = lambda **_kwargs: _FakeOpenAIClient(calls)  # type: ignore[misc]
    try:
        return OpenAICompatProvider()
    finally:
        openai.OpenAI = original  # type: ignore[misc]


def test_gemini_requests_temperature_zero() -> None:
    """The Gemini path must pin the temperature to 0, as the docs claim."""
    calls: list[dict] = []
    provider = _gemini_provider(calls)
    answer = provider.answer("grounded prompt")
    assert answer == "grounded answer"
    assert calls, "the Gemini client was never called"
    config = calls[0].get("config") or {}
    assert config.get("temperature") == 0


def test_gemini_keeps_the_plain_language_instruction() -> None:
    """The plain-language system instruction must reach the Gemini call."""
    calls: list[dict] = []
    provider = _gemini_provider(calls)
    provider.answer("grounded prompt", plain_language=True)
    contents = str(calls[0].get("contents"))
    assert PLAIN_LANGUAGE_SYSTEM in contents
    assert "grounded prompt" in contents


def test_openai_compat_requests_temperature_zero() -> None:
    """The OpenAI-compatible path must pin the temperature to 0 as well."""
    calls: list[dict] = []
    provider = _openai_provider(calls)
    answer = provider.answer("grounded prompt")
    assert answer == "grounded answer"
    assert calls, "the OpenAI-compatible client was never called"
    assert calls[0].get("temperature") == 0


def test_every_provider_pins_the_same_temperature() -> None:
    """Both remote providers must agree on the generation temperature."""
    assert GeminiProvider.TEMPERATURE == 0
    gemini_calls: list[dict] = []
    _gemini_provider(gemini_calls).answer("grounded prompt")
    openai_calls: list[dict] = []
    _openai_provider(openai_calls).answer("grounded prompt")
    gemini_temperature = (gemini_calls[0].get("config") or {}).get("temperature")
    assert gemini_temperature == openai_calls[0].get("temperature") == 0
