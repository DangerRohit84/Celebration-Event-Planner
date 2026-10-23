"""Persistence package: repository pattern with pluggable backends.

The former single-module ``storage.py`` is split by responsibility:
``protocol`` carries the shared interface, ``memory``/``memory_records``
implement the in-memory backend, the ``sqlite_*`` modules implement the
SQLite backend, and ``store`` manages the process-wide instance.
"""

from __future__ import annotations

from .memory import InMemoryStore as InMemoryStore
from .protocol import CapacityError as CapacityError
from .protocol import EventStore as EventStore
from .protocol import new_id as new_id
from .sqlite_store import SQLiteStore as SQLiteStore
from .store import build_store as build_store
from .store import get_store as get_store
from .store import reset_store as reset_store
