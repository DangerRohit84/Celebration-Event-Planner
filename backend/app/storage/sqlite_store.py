"""SQLite backend assembly: the full persistent event store."""

from __future__ import annotations

from .sqlite_budget import SQLiteBudget
from .sqlite_events import SQLiteEvents
from .sqlite_vendors import SQLiteVendors


class SQLiteStore(SQLiteBudget, SQLiteVendors, SQLiteEvents):
    """File-based persistent backend. Schema created on first use."""
