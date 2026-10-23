"""Security helpers: input sanitization and bounds.

Mirrors proven patterns from prior run:
- Text sanitization for user inputs.
- Filename sanitization (traversal-safe, control-char strip, length cap).
- Allowlisted CORS origins (see config.parse_allowed_origins).

The upload guards (magic-byte validation, pre-parse validation) live in
:mod:`backend.app.upload_guard` and are re-exported here so the historical
import path keeps working.
"""

from __future__ import annotations

import re
from pathlib import Path

from .upload_guard import ALLOWED_CONTENT_TYPES as ALLOWED_CONTENT_TYPES
from .upload_guard import PDF_MAGIC as PDF_MAGIC
from .upload_guard import validate_pdf_magic as validate_pdf_magic
from .upload_guard import validate_pre_parse as validate_pre_parse


def sanitize_text(value: object, max_len: int = 2000) -> str:
    """Strip control chars and cap length.

    Args:
        value: Arbitrary input to clean; non-strings are coerced first.
        max_len: Maximum number of characters kept in the result.

    Returns:
        The cleaned text, capped to ``max_len`` characters.
    """
    if not isinstance(value, str):
        value = str(value)
    cleaned = "".join(
        ch
        for ch in value
        if ch == "\n" or ch == "\t" or (ord(ch) >= 32 and ord(ch) != 127)
    )
    return cleaned[:max_len].strip()


def sanitize_filename(raw: str) -> str:
    """Basename only, traversal-safe, control-char stripped, length capped.

    Args:
        raw: Raw filename supplied by the client.

    Returns:
        A safe filename, falling back to "upload.pdf" when nothing survives
        sanitization.
    """
    name = Path(raw or "").name
    name = sanitize_text(name, 128)
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name or "upload.pdf"
