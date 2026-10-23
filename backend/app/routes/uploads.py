"""Upload route: accept, validate, and parse a PDF document."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..config import settings
from ..ingest import (
    DocumentCapacityError,
    DocumentError,
    get_document_store,
    parse_pdf,
)
from ..schemas import UploadResponse
from ..security import sanitize_filename, validate_pre_parse
from .deps import DOCUMENT_STORE_FULL_RETRY_AFTER_SECONDS

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> dict:  # noqa: B008
    """Upload and parse a PDF document.
    Args:
        file: Uploaded PDF payload, read with a bounded buffer.
    Returns:
        A mapping with the sanitized filename, size, acceptance status, the
        upload identifier, the page count, and the number of chunks kept.
    Raises:
        HTTPException: With status 413 when the file exceeds the size limit,
            status 400 when it fails PDF pre-parse validation or cannot be
            parsed (for example a scanned, image-only document), and status
            429 when the session document store is saturated.
    """
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="file too large (10 MB limit)")
    filename = sanitize_filename(file.filename or "")
    content_type = file.content_type or "application/octet-stream"
    try:
        validate_pre_parse(filename, content_type, len(raw), raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        # CPU-bound parse runs on a worker thread so a crafted PDF cannot
        # stall the event loop (and with it the whole service).
        document = await asyncio.to_thread(parse_pdf, raw, filename)
    except DocumentError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        get_document_store().add(document)
    except DocumentCapacityError as e:
        raise HTTPException(
            status_code=429,
            detail="document store full",
            headers={"Retry-After": str(DOCUMENT_STORE_FULL_RETRY_AFTER_SECONDS)},
        ) from e
    return {
        "filename": filename,
        "size": len(raw),
        "status": "accepted",
        "upload_id": document.document_id,
        "pages": document.pages,
        "chunks": len(document.chunks),
    }
