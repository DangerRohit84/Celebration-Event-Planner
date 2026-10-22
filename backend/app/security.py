"""Security helpers: input validation, sanitization, bounds.

Mirrors proven patterns from prior run:
- Bounded reads (MAX+1) to avoid OOM.
- Magic-byte validation before parse.
- Filename sanitization (traversal-safe, control-char strip, length cap).
- Text sanitization for user inputs.
- Allowlisted session IDs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import settings

PDF_MAGIC = b"%PDF-"
ALLOWED_CONTENT_TYPES = {"application/pdf", "application/octet-stream"}


def sanitize_text(value: object, max_len: int = 2000) -> str:
    """Strip control chars and cap length."""
    if not isinstance(value, str):
        value = str(value)
    cleaned = "".join(
        ch
        for ch in value
        if ch == "\n" or ch == "\t" or (ord(ch) >= 32 and ord(ch) != 127)
    )
    return cleaned[:max_len].strip()


def sanitize_filename(raw: str) -> str:
    """Basename only, traversal-safe, control-char stripped, length capped."""
    name = Path(raw or "").name
    name = sanitize_text(name, 128)
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name or "upload.pdf"


def validate_pdf_magic(raw_bytes: bytes | bytearray) -> bool:
    """Validate that bytes start with the PDF magic header."""
    if not isinstance(raw_bytes, (bytes, bytearray)):
        raise TypeError("invalid pdf magic")
    if not bytes(raw_bytes).startswith(PDF_MAGIC):
        raise ValueError("invalid pdf magic")
    return True


def validate_pre_parse(*args: Any, **kwargs: Any) -> bool:
    """Pre-parse guards. Single canonical style (legal):
       validate_pre_parse(filename, content_type, size_bytes, data)
    Also accepts legacy celebration style:
       validate_pre_parse(data, filename, content_type)
    Raises ValueError on failure.
    """
    # Resolve arguments (support both call styles).
    if len(args) == 4:
        filename, content_type, size, raw_bytes = args
    elif len(args) == 3 and isinstance(args[0], (bytes, bytearray)):
        raw_bytes, filename, content_type = args
        size = len(raw_bytes)
    elif len(args) == 3:
        filename, content_type, size = args
        raw_bytes = kwargs.get("data") or kwargs.get("raw_bytes") or b""
    else:
        filename = kwargs.get("filename", "")
        content_type = kwargs.get("content_type", "application/pdf")
        size = kwargs.get("size")
        raw_bytes = kwargs.get("raw_bytes") or kwargs.get("data") or b""

    if not isinstance(raw_bytes, (bytes, bytearray)):
        raw_bytes = b""
    raw_bytes = bytes(raw_bytes)
    if size is None:
        size = len(raw_bytes)
    try:
        size = int(size)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        size = len(raw_bytes)

    if not filename or not str(filename).lower().endswith(".pdf"):
        raise ValueError("PDF only: file must end with .pdf")
    if size is None or size <= 0:
        raise ValueError("Empty file: upload a valid PDF")
    if size > settings.max_upload_bytes:
        raise ValueError("File too large: max 10 MB")
    if len(raw_bytes) > settings.max_upload_bytes:
        raise ValueError("File too large: max 10 MB")
    if not raw_bytes or not raw_bytes.startswith(PDF_MAGIC):
        raise ValueError("invalid pdf magic")
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("PDF only: invalid content-type")
    return True


def sanitize_session_id(raw: object) -> str:
    """Allowlist [A-Za-z0-9_-], max 64. Empty -> '' (no session)."""
    if not raw:
        return ""
    if not isinstance(raw, str):
        # support FakeReq-like? no, expect str
        try:
            raw = str(raw)
        except Exception:  # noqa: BLE001
            return ""
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", raw)
    return cleaned[:64]
