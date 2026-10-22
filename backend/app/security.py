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
from typing import overload

from .config import settings

PDF_MAGIC = b"%PDF-"
ALLOWED_CONTENT_TYPES = {"application/pdf", "application/octet-stream"}


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


def validate_pdf_magic(raw_bytes: bytes | bytearray) -> bool:
    """Validate that bytes start with the PDF magic header.

    Args:
        raw_bytes: File bytes to inspect.

    Returns:
        True when the bytes carry the PDF magic header.

    Raises:
        TypeError: When the input is not a bytes-like object.
        ValueError: When the bytes do not start with the PDF magic header.
    """
    if not isinstance(raw_bytes, (bytes, bytearray)):
        raise TypeError("invalid pdf magic")
    if not bytes(raw_bytes).startswith(PDF_MAGIC):
        raise ValueError("invalid pdf magic")
    return True


@overload
def validate_pre_parse(  # noqa: D418 - every function needs a docstring here
    filename: str, content_type: str, size: int, data: bytes, /,
) -> bool:
    """Validate an upload given its filename, content type, size, and bytes.

    Args:
        filename: Name of the uploaded file.
        content_type: MIME type reported for the upload.
        size: Declared size of the upload in bytes.
        data: Raw bytes of the upload.

    Returns:
        True when the upload passes every pre-parse guard.
    """


@overload
def validate_pre_parse(  # noqa: D418 - every function needs a docstring here
    data: bytes, filename: str, content_type: str, /,
) -> bool:
    """Validate an upload given its bytes, filename, and content type.

    Args:
        data: Raw bytes of the upload; the size is derived from them.
        filename: Name of the uploaded file.
        content_type: MIME type reported for the upload.

    Returns:
        True when the upload passes every pre-parse guard.
    """


def validate_pre_parse(
    first: str | bytes,
    second: str,
    third: int | str,
    data: bytes | None = None,
    /,
) -> bool:
    """Validate an upload before parsing (single canonical style).

    Canonical style: validate_pre_parse(filename, content_type, size_bytes, data).
    Legacy celebration style: validate_pre_parse(data, filename, content_type).

    The two call shapes are distinguished at runtime by the type of the first
    argument, so the public API stays fully typed without ``*args`` or
    ``**kwargs``.

    Args:
        first: The filename for the canonical style, or the raw file bytes for
            the legacy style.
        second: The content type for the canonical style, or the filename for
            the legacy style.
        third: The byte size for the canonical style, or the content type for
            the legacy style.
        data: The raw file bytes for the canonical style; unused in the
            legacy style, where the size is derived from the bytes.

    Returns:
        True when the upload passes every pre-parse guard.

    Raises:
        TypeError: When the arguments do not match either supported call
            shape.
        ValueError: When the filename, size, content type, or magic bytes fail
            validation.
    """
    if isinstance(first, (bytes, bytearray)):
        # Legacy style: (data, filename, content_type).
        if data is not None:
            raise TypeError(
                "validate_pre_parse() accepts either "
                "(filename, content_type, size, data) "
                "or (data, filename, content_type)",
            )
        raw_bytes = bytes(first)
        filename = second
        content_type = str(third)
        size: int | str = len(raw_bytes)
    else:
        # Canonical style: (filename, content_type, size, data).
        if data is None:
            raise TypeError(
                "validate_pre_parse() requires the file bytes: "
                "call it as (filename, content_type, size, data)",
            )
        filename = first
        content_type = second
        size = third
        raw_bytes = bytes(data)

    try:
        size = int(str(size))
    except (TypeError, ValueError):
        size = len(raw_bytes)

    if not filename or not str(filename).lower().endswith(".pdf"):
        raise ValueError("PDF only: file must end with .pdf")
    if size <= 0:
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
    """Allowlist [A-Za-z0-9_-], max 64. Empty -> '' (no session).

    Args:
        raw: Raw session identifier supplied by the client.

    Returns:
        The allowlisted session identifier, or an empty string when absent.
    """
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
