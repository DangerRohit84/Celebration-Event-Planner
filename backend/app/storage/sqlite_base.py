"""SQLite backend foundation: schema, connections, and row converters."""

from __future__ import annotations

import sqlite3
import threading
from datetime import date, datetime
from pathlib import Path

from ..config import settings
from ..models import Event, EventType, Vendor, VendorStatus


class SQLiteBase:
    """SQLite plumbing shared by every backend operation group."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        event_type TEXT NOT NULL,
        event_date TEXT NOT NULL,
        guest_count INTEGER NOT NULL,
        budget_total REAL NOT NULL,
        theme TEXT DEFAULT '',
        location TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS budget_lines (
        id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        category TEXT NOT NULL,
        allocated REAL NOT NULL,
        spent REAL DEFAULT 0.0,
        notes TEXT DEFAULT '',
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS milestones (
        id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        title TEXT NOT NULL,
        due_date TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        notes TEXT DEFAULT '',
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS vendors (
        id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        category TEXT NOT NULL,
        name TEXT DEFAULT '',
        status TEXT DEFAULT 'not_started',
        cost_estimate REAL DEFAULT 0.0,
        contact TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    );
    """

    def __init__(self, db_path: str | Path, max_events: int | None = None):
        """Initialize the store and create the SQLite schema if needed.
        Args:
            db_path: Filesystem path of the SQLite database file.
            max_events: Maximum number of events to hold; defaults to the
                configured ``settings.max_store_events`` limit.
        """
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._max = max_events if max_events is not None else settings.max_store_events
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection with row access and foreign keys enabled.
        Returns:
            A new connection configured for dictionary-like row access.
        """
        conn = sqlite3.connect(str(self._path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _row_to_event(self, r: sqlite3.Row) -> Event:
        """Convert a database row into an event entity.
        Args:
            r: Row read from the ``events`` table.
        Returns:
            The corresponding event entity.
        """
        try:
            et = EventType(r["event_type"])
        except ValueError:
            et = EventType.OTHER
        return Event(
            id=r["id"],
            name=r["name"],
            event_type=et,
            event_date=date.fromisoformat(r["event_date"]),
            guest_count=r["guest_count"],
            budget_total=r["budget_total"],
            theme=r["theme"],
            location=r["location"],
            notes=r["notes"],
            created_at=datetime.fromisoformat(r["created_at"]),
            updated_at=datetime.fromisoformat(r["updated_at"]),
        )

    def _row_to_vendor(self, r: sqlite3.Row) -> Vendor:
        """Convert a database row into a vendor entity.
        Args:
            r: Row read from the ``vendors`` table.
        Returns:
            The corresponding vendor entity.
        """
        try:
            st = VendorStatus(r["status"])
        except ValueError:
            st = VendorStatus.NOT_STARTED
        return Vendor(
            id=r["id"],
            event_id=r["event_id"],
            category=r["category"],
            name=r["name"],
            status=st,
            cost_estimate=r["cost_estimate"],
            contact=r["contact"],
            notes=r["notes"],
        )
