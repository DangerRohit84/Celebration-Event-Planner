"""Document ingestion: PDF parsing and section-aware chunking.

Responsibilities:
1. Parse an uploaded PDF into its page count and extractable text, using
   ``pypdf``. The byte cap is enforced by the upload route before this
   module is called, so the parser never sees an unbounded buffer.
2. Split the extracted text into chunks that respect section and sentence
   boundaries, so a chunk is a coherent passage rather than a fixed-size
   slice of arbitrary characters.
3. Keep a bounded, in-memory registry of the parsed documents so the
   ideas/ask flow can inject the most relevant excerpts as extra context.
   The registry is sized by the ``MAX_DOCUMENTS`` setting and refuses new
   documents when it is saturated, so the upload route can answer 429.

The module is deliberately free of HTTP concerns: it raises
:class:`DocumentError` and :class:`DocumentCapacityError`, and the route
translates them into a 400 and a 429 respectively.
"""

from __future__ import annotations

import io
import re
import threading
import uuid
from dataclasses import dataclass

from pypdf import PdfReader

from .config import settings
from .models import Chunk

# Sentence boundary: a terminator followed by whitespace.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
# Words used to score a chunk against a query.
_TOKEN = re.compile(r"[a-z0-9]+")

DEFAULT_CHUNK_CHARS = 800
DEFAULT_MAX_DOCUMENTS = 10
DEFAULT_RELEVANT_CHUNKS = 3


class DocumentError(Exception):
    """Raised when an uploaded document cannot be parsed (maps to HTTP 400)."""


class DocumentCapacityError(Exception):
    """Raised when the document store is at capacity (maps to HTTP 429)."""


@dataclass(frozen=True)
class ParsedDocument:
    """An uploaded document that has been parsed into retrievable chunks."""

    document_id: str
    filename: str
    pages: int
    text_length: int
    chunks: tuple[Chunk, ...]


def _is_heading(line: str) -> bool:
    """Report whether a line looks like a section heading.

    A heading is a short line that is not a sentence and is written in
    Title Case or ALL CAPS - the two conventions used by the event-planning
    documents this app accepts.

    Args:
        line: A single stripped line of extracted document text.

    Returns:
        True when the line should be treated as a section boundary.
    """
    if not line or len(line) > 80:
        return False
    if line.endswith((".", ",", ";", ":", "!", "?")):
        return False
    words = line.split()
    if not words or len(words) > 12:
        return False
    return line == line.title() or line == line.upper()


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split extracted text into labelled sections.

    A section starts at a heading-like line and runs until the next heading
    or a blank line. Sections without a heading are labelled with an empty
    string.

    Args:
        text: Extracted text of one page.

    Returns:
        A list of ``(section_label, section_body)`` pairs in document order.
    """
    sections: list[tuple[str, str]] = []
    label = ""
    body: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if body:
                sections.append((label, " ".join(body).strip()))
            body.clear()
            label = ""
            continue
        if _is_heading(line):
            if body:
                sections.append((label, " ".join(body).strip()))
                body.clear()
            elif label:
                # A heading with no body of its own still carries content.
                sections.append((label, label))
            label = line
            continue
        body.append(line)
    if body:
        sections.append((label, " ".join(body).strip()))
    elif label:
        sections.append((label, label))
    return sections


def _chunk_section(body: str, max_chars: int) -> list[str]:
    """Split one section into chunks that end on sentence boundaries.

    Sentences are accumulated until the chunk would exceed ``max_chars``.
    A single sentence longer than the limit is hard-split, because there is
    no sentence boundary inside it to preserve.

    Args:
        body: The text of a single section.
        max_chars: Maximum number of characters per chunk.

    Returns:
        The chunk texts produced from the section.
    """
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(body) if s.strip()]
    if not sentences:
        return []
    chunks: list[str] = []
    buffer = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            for start in range(0, len(sentence), max_chars):
                chunks.append(sentence[start : start + max_chars])
            continue
        if not buffer:
            buffer = sentence
        elif len(buffer) + 1 + len(sentence) <= max_chars:
            buffer = f"{buffer} {sentence}"
        else:
            chunks.append(buffer)
            buffer = sentence
    if buffer:
        chunks.append(buffer)
    return chunks


def chunk_text(text: str, *, max_chars: int = DEFAULT_CHUNK_CHARS) -> list[str]:
    """Split plain text into section-aware chunks.

    Args:
        text: The text to split.
        max_chars: Maximum number of characters per chunk.

    Returns:
        The chunk texts, in document order.
    """
    chunks: list[str] = []
    for _label, body in _split_sections(text):
        chunks.extend(_chunk_section(body, max_chars))
    return chunks


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


class DocumentStore:
    """Bounded, thread-safe registry of parsed documents.

    The store keeps at most ``max_documents`` documents. When it is
    saturated it refuses new documents instead of silently dropping an
    older one, so the caller learns about the limit (the upload route
    answers with HTTP 429 and a ``Retry-After`` header). The most recent
    upload acts as the session document, which is the one whose excerpts
    are injected into idea prompts.
    """

    def __init__(self, max_documents: int = DEFAULT_MAX_DOCUMENTS) -> None:
        """Create an empty document store.

        Args:
            max_documents: Maximum number of documents kept in the store.
        """
        self._max = max(1, max_documents)
        self._documents: dict[str, ParsedDocument] = {}
        self._lock = threading.Lock()

    @property
    def max_documents(self) -> int:
        """Return the configured capacity of the store.

        Returns:
            The maximum number of documents the store keeps.
        """
        return self._max

    @property
    def count(self) -> int:
        """Return the number of documents currently held.

        Returns:
            The number of stored documents.
        """
        with self._lock:
            return len(self._documents)

    def add(self, document: ParsedDocument) -> None:
        """Store a parsed document.

        Args:
            document: The document to store.

        Raises:
            DocumentCapacityError: When the store already holds its maximum
                number of documents.
        """
        with self._lock:
            if (
                document.document_id not in self._documents
                and len(self._documents) >= self._max
            ):
                raise DocumentCapacityError(
                    f"document store full ({self._max} documents)",
                )
            self._documents[document.document_id] = document

    def get(self, document_id: str) -> ParsedDocument | None:
        """Look up a stored document by identifier.

        Args:
            document_id: Identifier of the document to retrieve.

        Returns:
            The stored document, or None when the identifier is unknown.
        """
        with self._lock:
            return self._documents.get(document_id)

    def latest(self) -> ParsedDocument | None:
        """Return the most recently stored document.

        Returns:
            The newest document in the store, or None when it is empty.
        """
        with self._lock:
            if not self._documents:
                return None
            return next(reversed(self._documents.values()))

    def clear(self) -> None:
        """Remove every stored document.

        Returns:
            None.
        """
        with self._lock:
            self._documents.clear()


def build_document_store() -> DocumentStore:
    """Create a document store sized by the configured maximum.

    The capacity comes from ``MAX_DOCUMENTS`` (see
    :func:`backend.app.config.Settings.max_documents`), so the documented
    environment variable really bounds the session document store.

    Returns:
        A new, empty document store.
    """
    return DocumentStore(max_documents=max(1, settings.max_documents))


_document_store = build_document_store()


def get_document_store() -> DocumentStore:
    """Return the process-wide document store.

    Returns:
        The shared document store instance.
    """
    return _document_store


def reset_document_store() -> None:
    """Rebuild the process-wide document store (tests).

    The store is rebuilt rather than merely cleared so that it always
    reflects the currently configured ``MAX_DOCUMENTS`` value.

    Returns:
        None.
    """
    global _document_store
    _document_store = build_document_store()
