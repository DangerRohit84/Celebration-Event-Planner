"""Application configuration (env-driven, no secrets in code).

All settings are read from environment variables with safe defaults.
Secrets (API keys) are NEVER hardcoded; .env is gitignored.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# An origin is "scheme://host" with an optional numeric port. Anything else
# (a bare host, a path, a wildcard, an ftp:// scheme) is rejected outright.
_ORIGIN_RE = re.compile(r"^https?://[A-Za-z0-9._-]+(:\d{1,5})?$")


def parse_allowed_origins(raw: str) -> list[str]:
    """Parse a comma-separated CORS origin allowlist into safe entries.

    The parser is deliberately strict: it is the single gate that guarantees
    a wildcard can never reach the CORS middleware, and it drops malformed
    entries instead of forwarding them. An empty result is a valid, safe
    outcome - it means "allow no cross-origin caller".

    Args:
        raw: Raw configuration value, typically a comma-separated list of
            origins such as "https://app.example.com,https://admin.example.com".

    Returns:
        The validated origins, in configuration order, without duplicates.
        Wildcards and malformed entries are dropped, so the result may be
        empty but never contains "*".
    """
    origins: list[str] = []
    for entry in (raw or "").split(","):
        candidate = entry.strip()
        if not candidate:
            continue
        if "*" in candidate:
            # Never allow a wildcard, not even alongside other entries.
            continue
        if not _ORIGIN_RE.match(candidate):
            continue
        if candidate not in origins:
            origins.append(candidate)
    return origins


def _int(name: str, default: int) -> int:
    """Parse an integer env var, falling back to default on failure.

    Args:
        name: Environment variable name to read.
        default: Value returned when the variable is unset or unparsable.

    Returns:
        The parsed integer value, or the default.
    """
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool) -> bool:
    """Parse a boolean env var.

    Args:
        name: Environment variable name to read.
        default: Value returned when the variable is unset.

    Returns:
        True when the variable holds a truthy token ("1", "true", "yes", "on"),
        otherwise False.
    """
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
    max_rate_buckets: int = _int("MAX_RATE_BUCKETS", 10000)
    max_upload_bytes: int = _int("MAX_UPLOAD_BYTES", 10 * 1024 * 1024)
    max_store_events: int = _int("MAX_STORE_EVENTS", 5000)
    max_store_chunks: int = _int("MAX_STORE_CHUNKS", 1000)
    demo_mode: bool = _bool("DEMO_MODE", True)

    # App
    port: int = _int("PORT", 8000)
    log_level: str = os.getenv("LOG_LEVEL", "info")

    @property
    def allowed_origins(self) -> list[str]:
        """Return the allowlisted frontend origins.

        The list is produced by :func:`parse_allowed_origins`, so wildcards
        and malformed values are dropped. An empty list means no cross-origin
        caller is allowed - the CORS middleware then omits the
        ``Access-Control-Allow-Origin`` header and the browser blocks the
        request.

        Returns:
            The validated, de-duplicated origins in configuration order.
        """
        return parse_allowed_origins(self.frontend_origin)

    @property
    def db_path(self) -> Path:
        """Resolve the sqlite file path for local dev.

        Returns:
            The filesystem path of the SQLite database file.
        """
        # Resolve sqlite file path for local dev.
        url = self.database_url
        if url.startswith("sqlite:///"):
            return Path(url.replace("sqlite:///", "", 1))
        return Path("./data/events.db")


settings = Settings()
