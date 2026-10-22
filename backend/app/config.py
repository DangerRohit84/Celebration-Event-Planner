"""Application configuration (env-driven, no secrets in code).

All settings are read from environment variables with safe defaults.
Secrets (API keys) are NEVER hardcoded; .env is gitignored.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    """Parse an integer env var, falling back to default on failure."""
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool) -> bool:
    """Parse a boolean env var."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    # LLM
    llm_provider: str = os.getenv("LLM_PROVIDER", "echo")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "")

    # Storage (pluggable backend)
    store_backend: str = os.getenv("STORE_BACKEND", "sqlite")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/events.db")

    # Security
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:8000")
    rate_limit_per_min: int = _int("RATE_LIMIT_PER_MIN", 200)
    max_upload_bytes: int = _int("MAX_UPLOAD_BYTES", 10 * 1024 * 1024)
    max_store_events: int = _int("MAX_STORE_EVENTS", 5000)
    max_store_chunks: int = _int("MAX_STORE_CHUNKS", 1000)
    demo_mode: bool = _bool("DEMO_MODE", True)

    # App
    port: int = _int("PORT", 8000)
    log_level: str = os.getenv("LOG_LEVEL", "info")

    @property
    def allowed_origins(self) -> list[str]:
        """Return the allowlisted frontend origins."""
        # Never wildcard; allowlist only.
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]

    @property
    def db_path(self) -> Path:
        """Resolve the sqlite file path for local dev."""
        # Resolve sqlite file path for local dev.
        url = self.database_url
        if url.startswith("sqlite:///"):
            return Path(url.replace("sqlite:///", "", 1))
        return Path("./data/events.db")


settings = Settings()
