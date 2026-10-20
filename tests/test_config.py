"""Config tests."""
from backend.app.config import settings


def test_defaults():
    assert settings.llm_provider in ("echo", "gemini", "openai-compat", "openai", "openai_compat")
    assert settings.rate_limit_per_min > 0
    assert settings.max_upload_bytes > 0


def test_allowed_origins_no_wildcard():
    for o in settings.allowed_origins:
        assert o != "*"
