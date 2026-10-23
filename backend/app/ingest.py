"""Document ingestion: PDF parsing and chunk relevance.

Responsibilities:
1. Parse an uploaded PDF into its page count and extractable text, using
   ``pypdf``. The byte cap is enforced by the upload route before this
   module is called, so the parser never sees an unbounded buffer.
2. Score the parsed chunks against a follow-up question so the ideas/ask
   flow can inject the most relevant excerpts as extra context.

Chunking itself lives in :mod:`backend.app.chunking` and the bounded
document registry lives in :mod:`backend.app.docstore`; both are
re-exported here so the historical import path keeps working.

The module is deliberately free of HTTP concerns: it raises
:class:`DocumentError` (and, via the store, :class:`DocumentCapacityError`),
and the route translates them into a 400 and a 429 respectively.
"""

from __future__ import annotations

import io
import re
import uuid

from pypdf import PdfReader

from .chunking import DEFAULT_CHUNK_CHARS, _chunk_section, _split_sections
from .chunking import chunk_text as chunk_text
from .config import settings
from .docstore import DocumentCapacityError as DocumentCapacityError
from .docstore import DocumentStore as DocumentStore
from .docstore import ParsedDocument
from .docstore import get_document_store as get_document_store
from .docstore import reset_document_store as reset_document_store
from .models import Chunk

# Words used to score a chunk against a query.
_TOKEN = re.compile(r"[a-z0-9]+")

DEFAULT_RELEVANT_CHUNKS = 3


class DocumentError(Exception):
    """Raised when an uploaded document cannot be parsed (maps to HTTP 400)."""


def parse_pdf(raw: bytes, filename: str) -> ParsedDocument:
    """Parse a PDF into a document with pages and section-aware chunks.

    Args:
        raw: The raw bytes of the uploaded PDF.
        filename: The sanitized filename, used only for reporting.

    Returns:
        The parsed document, carrying its page count and chunks.

    Raises:
        DocumentError: When the PDF cannot be opened, has no pages, or
            contains no extractable text (for example a scanned image-only
            document).
    """
    document_id = uuid.uuid4().hex
    try:
        reader = PdfReader(io.BytesIO(raw))
        pages = list(reader.pages)
    except Exception as exc:  # noqa: BLE001
        raise DocumentError(
            f"could not read '{filename}' as a PDF ({type(exc).__name__})",
        ) from exc
    if not pages:
        raise DocumentError(f"'{filename}' has no pages")

    max_chunks = max(1, settings.max_store_chunks)
    chunks: list[Chunk] = []
    text_length = 0
    for page_number, page in enumerate(pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            page_text = ""
        text_length += len(page_text)
        for label, body in _split_sections(page_text):
            for text in _chunk_section(body, DEFAULT_CHUNK_CHARS):
                chunks.append(
                    Chunk(
                        chunk_id=f"{document_id}-{len(chunks) + 1}",
                        doc_id=document_id,
                        page=page_number,
                        clause=label,
                        text=text,
                    ),
                )
                if len(chunks) >= max_chunks:
                    break
            if len(chunks) >= max_chunks:
                break
        if len(chunks) >= max_chunks:
            break

    if text_length == 0 or not chunks:
        raise DocumentError(
            f"'{filename}' contains no extractable text "
            "(it may be a scanned image or an encrypted document)",
        )
    return ParsedDocument(
        document_id=document_id,
        filename=filename,
        pages=len(pages),
        text_length=text_length,
        chunks=tuple(chunks),
    )


def relevant_chunks(
    document: ParsedDocument,
    query: str,
    limit: int = DEFAULT_RELEVANT_CHUNKS,
) -> list[str]:
    """Return the chunks of a document that best match a query.

    Args:
        document: The parsed document to search.
        query: The user's question.
        limit: Maximum number of chunks to return.

    Returns:
        The texts of the best-matching chunks, most relevant first. An empty
        list when the document holds no chunks.
    """
    if not document.chunks:
        return []
    query_tokens = set(_TOKEN.findall((query or "").lower()))
    scored: list[tuple[float, str]] = []
    for chunk in document.chunks:
        tokens = set(_TOKEN.findall(chunk.text.lower()))
        if not tokens or not query_tokens:
            continue
        overlap = len(tokens & query_tokens)
        if overlap == 0:
            continue
        scored.append((overlap / len(query_tokens), chunk.text))
    if not scored:
        return []
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [text for _score, text in scored[:limit]]
