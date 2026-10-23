"""Process-wide store management: build, cache, and reset the backend."""

from __future__ import annotations

import threading

from ..config import settings
from .memory import InMemoryStore
from .protocol import EventStore
from .sqlite_store import SQLiteStore


def build_store() -> EventStore:
    """Build the event store backend selected by configuration.
    Returns:
        An in-memory store when ``STORE_BACKEND`` is ``memory``, otherwise a
        SQLite-backed store.
    """
    backend = settings.store_backend.lower()
    if backend == "memory":
        return InMemoryStore()
    # default: persistent sqlite
    return SQLiteStore(settings.db_path)


_store: EventStore | None = None
_store_lock = threading.Lock()


def get_store() -> EventStore:
    """Return the process-wide event store, initializing it on first use.
    Returns:
        The shared event store instance for the configured backend.
    """
    global _store
    with _store_lock:
        if _store is None:
            _store = build_store()
        return _store


def reset_store(store: EventStore | None = None) -> None:
    """Replace the process-wide event store (tests).
    Args:
        store: Replacement store instance; None clears the cached store so the
            next :func:`get_store` call rebuilds it from configuration.
    """
    global _store
    with _store_lock:
        _store = store
