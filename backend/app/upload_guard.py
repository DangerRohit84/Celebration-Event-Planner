"""Upload guards: pre-parse validation of uploaded documents.

Mirrors proven patterns from prior run:
- Bounded reads (MAX+1) to avoid OOM (enforced by the upload route).
- Magic-byte validation before parse.
- Content-type allowlist.

Filename sanitization and text sanitization live in
:mod:`backend.app.security`; both modules are re-exported there so the
historical import path keeps working.
"""

from __future__ import annotations

from typing import overload

from .config import settings

PDF_MAGIC = b"%PDF-"
ALLOWED_CONTENT_TYPES = {"application/pdf", "application/octet-stream"}


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
    if not isinstance(raw_bytes, bytes | bytearray):
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
        first: Filename (canonical) or raw bytes (legacy).
        second: Content type (canonical) or filename (legacy).
        third: Byte size (canonical) or content type (legacy).
        data: Raw file bytes (canonical); unused in the legacy style.

    Returns:
        True when the upload passes every pre-parse guard.

    Raises:
        TypeError: When the arguments do not match either supported call shape.
        ValueError: When the filename, size, content type, or magic bytes fail validation.
    """
    if isinstance(first, bytes | bytearray):
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
    validate_pdf_magic(raw_bytes)
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("PDF only: invalid content-type")
    return True
