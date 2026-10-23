"""Bounded, thread-safe registry of parsed documents.

The store keeps at most ``max_documents`` documents. When it is saturated
it refuses new documents instead of silently dropping an older one, so the
caller learns about the limit (the upload route answers with HTTP 429 and
a ``Retry-After`` header). The most recent upload acts as the session
document, which is the one whose excerpts are injected into idea prompts.

The record the store keeps is :class:`ParsedDocument`: a parsed upload
carrying its page count and retrievable chunks.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from .models import Chunk

DEFAULT_MAX_DOCUMENTS = 10


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


class DocumentStore:
    """Bounded, thread-safe registry of parsed documents."""

    def __init__(self, max_documents: int = DEFAULT_MAX_DOCUMENTS) -> None:
        """Create an empty store.

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
        """Remove every stored document."""
        with self._lock:
            self._documents.clear()


def build_document_store() -> DocumentStore:
    """Create a document store sized by the configured ``MAX_DOCUMENTS``.

    Returns:
        A new, empty document store.
    """
    from .config import settings

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
    """
    global _document_store
    _document_store = build_document_store()
