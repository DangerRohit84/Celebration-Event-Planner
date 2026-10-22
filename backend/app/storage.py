"""Persistence layer: repository pattern with pluggable backend.

Design goals (learned from prior run):
- Never in-memory-only: default backend is SQLite (file-based, persistent).
- Pluggable: STORE_BACKEND=sqlite|memory; swap to Postgres via DATABASE_URL
  without changing callers (repository interface is the contract).
- Bounded: MAX_STORE_EVENTS enforced; 429 when full.
- Thread-safe: a single lock guards mutations.
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from .config import settings
from .models import BudgetLine, Event, Guest, TimelineMilestone, Vendor


def new_id() -> str:
    """Generate a new unique id.

    Returns:
        A hexadecimal identifier derived from a fresh UUID4.
    """
    return uuid.uuid4().hex


class CapacityError(Exception):
    """Raised when the store is at capacity (maps to HTTP 429)."""


class EventStore(Protocol):
    """Repository contract. Implementations must be thread-safe."""

    def create_event(self, event: Event) -> Event:
        """Create and persist a new event.

        Args:
            event: Event to persist, keyed by its own identifier.

        Returns:
            The persisted event.

        Raises:
            CapacityError: When the bounded event store is saturated.
        """
        ...

    def get_event(self, event_id: str) -> Event | None:
        """Look up a single event by identifier.

        Args:
            event_id: Identifier of the event to retrieve.

        Returns:
            The stored event, or None when no event has that identifier.
        """
        ...

    def list_events(self, limit: int = 100, offset: int = 0) -> list[Event]:
        """List stored events with pagination.

        Args:
            limit: Maximum number of events to return.
            offset: Number of events to skip before collecting results.

        Returns:
            The requested page of stored events.
        """
        ...

    def update_event(self, event: Event) -> Event:
        """Replace an existing event with the supplied values.

        Args:
            event: Event carrying the new values; its identifier is the key.

        Returns:
            The updated event.

        Raises:
            KeyError: When no event with that identifier is stored.
        """
        ...

    def delete_event(self, event_id: str) -> bool:
        """Delete an event and its dependent records.

        Args:
            event_id: Identifier of the event to delete.

        Returns:
            True when an event was removed, False when the identifier is unknown.
        """
        ...

    def count_events(self) -> int:
        """Count the stored events.

        Returns:
            The number of events currently stored.
        """
        ...

    def add_budget_line(self, line: BudgetLine) -> BudgetLine:
        """Append a budget line to an event.

        Args:
            line: Budget line to store against its event.

        Returns:
            The stored budget line.
        """
        ...

    def list_budget(self, event_id: str) -> list[BudgetLine]:
        """List the budget lines of an event.

        Args:
            event_id: Identifier of the event whose budget is requested.

        Returns:
            The budget lines for the event, empty when it has none.
        """
        ...

    def add_milestone(self, m: TimelineMilestone) -> TimelineMilestone:
        """Append a timeline milestone to an event.

        Args:
            m: Milestone to store against its event.

        Returns:
            The stored milestone.
        """
        ...

    def list_timeline(self, event_id: str) -> list[TimelineMilestone]:
        """List the timeline milestones of an event.

        Args:
            event_id: Identifier of the event whose timeline is requested.

        Returns:
            The milestones for the event, empty when it has none.
        """
        ...

    def add_vendor(self, v: Vendor) -> Vendor:
        """Append a vendor to an event.

        Args:
            v: Vendor to store against its event.

        Returns:
            The stored vendor.
        """
        ...

    def list_vendors(self, event_id: str) -> list[Vendor]:
        """List the vendors of an event.

        Args:
            event_id: Identifier of the event whose vendors are requested.

        Returns:
            The vendors for the event, empty when it has none.
        """
        ...

    def update_vendor(self, v: Vendor) -> Vendor:
        """Replace an existing vendor with the supplied values.

        Args:
            v: Vendor carrying the new values; its identifier is the key.

        Returns:
            The updated vendor.

        Raises:
            KeyError: When no vendor with that identifier is stored.
        """
        ...

    def add_guest(self, g: Guest) -> Guest:
        """Append a guest to an event.

        Args:
            g: Guest to store against its event.

        Returns:
            The stored guest.
        """
        ...

    def list_guests(self, event_id: str) -> list[Guest]:
        """List the guests of an event.

        Args:
            event_id: Identifier of the event whose guests are requested.

        Returns:
            The guests for the event, empty when it has none.
        """
        ...


# ---------- In-memory backend (tests + ephemeral) ----------


class InMemoryStore:
    """In-memory event store (tests + ephemeral)."""

    def __init__(self, max_events: int | None = None):
        """Initialize an empty in-memory store.

        Args:
            max_events: Maximum number of events to hold; defaults to the
                configured ``settings.max_store_events`` limit.
        """
        self._max = max_events if max_events is not None else settings.max_store_events
        self._events: dict[str, Event] = {}
        self._budget: dict[str, list[BudgetLine]] = {}
        self._timeline: dict[str, list[TimelineMilestone]] = {}
        self._vendors: dict[str, list[Vendor]] = {}
        self._guests: dict[str, list[Guest]] = {}
        self._lock = threading.Lock()

    def _guard_capacity(self) -> None:
        """Ensure the store is not already holding the maximum event count.

        Raises:
            CapacityError: When the bounded event store is saturated.
        """
        if len(self._events) >= self._max:
            raise CapacityError("event store full")

    def create_event(self, event: Event) -> Event:
        """Create and persist a new event in memory.

        Args:
            event: Event to persist, keyed by its own identifier.

        Returns:
            The persisted event.

        Raises:
            CapacityError: When the bounded event store is saturated.
        """
        with self._lock:
            self._guard_capacity()
            self._events[event.id] = event
            self._budget[event.id] = []
            self._timeline[event.id] = []
            self._vendors[event.id] = []
            self._guests[event.id] = []
            return event

    def get_event(self, event_id: str) -> Event | None:
        """Look up a single event by identifier.

        Args:
            event_id: Identifier of the event to retrieve.

        Returns:
            The stored event, or None when no event has that identifier.
        """
        with self._lock:
            return self._events.get(event_id)

    def list_events(self, limit: int = 100, offset: int = 0) -> list[Event]:
        """List stored events with pagination.

        Args:
            limit: Maximum number of events to return.
            offset: Number of events to skip before collecting results.

        Returns:
            The requested page of stored events.
        """
        with self._lock:
            items = list(self._events.values())
            return items[offset : offset + limit]

    def update_event(self, event: Event) -> Event:
        """Replace an existing event with the supplied values.

        Args:
            event: Event carrying the new values; its identifier is the key.

        Returns:
            The updated event.

        Raises:
            KeyError: When no event with that identifier is stored.
        """
        with self._lock:
            if event.id not in self._events:
                raise KeyError(event.id)
            self._events[event.id] = event
            return event

    def delete_event(self, event_id: str) -> bool:
        """Delete an event and its dependent records.

        Args:
            event_id: Identifier of the event to delete.

        Returns:
            True when an event was removed, False when the identifier is unknown.
        """
        with self._lock:
            if event_id not in self._events:
                return False
            del self._events[event_id]
            self._budget.pop(event_id, None)
            self._timeline.pop(event_id, None)
            self._vendors.pop(event_id, None)
            self._guests.pop(event_id, None)
            return True

    def count_events(self) -> int:
        """Count the stored events.

        Returns:
            The number of events currently stored.
        """
        with self._lock:
            return len(self._events)

    def add_budget_line(self, line: BudgetLine) -> BudgetLine:
        """Append a budget line to an event.

        Args:
            line: Budget line to store against its event.

        Returns:
            The stored budget line.
        """
        with self._lock:
            self._budget.setdefault(line.event_id, []).append(line)
            return line

    def list_budget(self, event_id: str) -> list[BudgetLine]:
        """List the budget lines of an event.

        Args:
            event_id: Identifier of the event whose budget is requested.

        Returns:
            The budget lines for the event, empty when it has none.
        """
        with self._lock:
            return list(self._budget.get(event_id, []))

    def add_milestone(self, m: TimelineMilestone) -> TimelineMilestone:
        """Append a timeline milestone to an event.

        Args:
            m: Milestone to store against its event.

        Returns:
            The stored milestone.
        """
        with self._lock:
            self._timeline.setdefault(m.event_id, []).append(m)
            return m

    def list_timeline(self, event_id: str) -> list[TimelineMilestone]:
        """List the timeline milestones of an event.

        Args:
            event_id: Identifier of the event whose timeline is requested.

        Returns:
            The milestones for the event, empty when it has none.
        """
        with self._lock:
            return list(self._timeline.get(event_id, []))

    def add_vendor(self, v: Vendor) -> Vendor:
        """Append a vendor to an event.

        Args:
            v: Vendor to store against its event.

        Returns:
            The stored vendor.
        """
        with self._lock:
            self._vendors.setdefault(v.event_id, []).append(v)
            return v

    def list_vendors(self, event_id: str) -> list[Vendor]:
        """List the vendors of an event.

        Args:
            event_id: Identifier of the event whose vendors are requested.

        Returns:
            The vendors for the event, empty when it has none.
        """
        with self._lock:
            return list(self._vendors.get(event_id, []))

    def update_vendor(self, v: Vendor) -> Vendor:
        """Replace an existing vendor with the supplied values.

        Args:
            v: Vendor carrying the new values; its identifier is the key.

        Returns:
            The updated vendor.

        Raises:
            KeyError: When no vendor with that identifier is stored.
        """
        with self._lock:
            lst = self._vendors.get(v.event_id, [])
            for i, existing in enumerate(lst):
                if existing.id == v.id:
                    lst[i] = v
                    return v
            raise KeyError(v.id)

    def add_guest(self, g: Guest) -> Guest:
        """Append a guest to an event.

        Args:
            g: Guest to store against its event.

        Returns:
            The stored guest.
        """
        with self._lock:
            self._guests.setdefault(g.event_id, []).append(g)
            return g

    def list_guests(self, event_id: str) -> list[Guest]:
        """List the guests of an event.

        Args:
            event_id: Identifier of the event whose guests are requested.

        Returns:
            The guests for the event, empty when it has none.
        """
        with self._lock:
            return list(self._guests.get(event_id, []))


# ---------- SQLite backend (default, persistent) ----------


class SQLiteStore:
    """File-based persistent backend. Schema created on first use."""

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
    CREATE TABLE IF NOT EXISTS guests (
        id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        name TEXT NOT NULL,
        rsvp TEXT DEFAULT 'pending',
        dietary TEXT DEFAULT '',
        plus_one INTEGER DEFAULT 0,
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

    # --- events ---
    def create_event(self, event: Event) -> Event:
        """Create and persist a new event in SQLite.

        Args:
            event: Event to persist, keyed by its own identifier.

        Returns:
            The persisted event.

        Raises:
            CapacityError: When the bounded event store is saturated.
        """
        with self._lock:
            # count without re-locking
            with self._connect() as conn:
                cnt = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            if cnt >= self._max:
                raise CapacityError("event store full")
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO events (id,name,event_type,event_date,guest_count,budget_total,theme,location,notes,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        event.id,
                        event.name,
                        event.event_type.value
                        if hasattr(event.event_type, "value")
                        else str(event.event_type),
                        event.event_date.isoformat(),
                        event.guest_count,
                        event.budget_total,
                        event.theme,
                        event.location,
                        event.notes,
                        event.created_at.isoformat(),
                        event.updated_at.isoformat(),
                    ),
                )
                conn.commit()
            return event

    def get_event(self, event_id: str) -> Event | None:
        """Look up a single event by identifier.

        Args:
            event_id: Identifier of the event to retrieve.

        Returns:
            The stored event, or None when no event has that identifier.
        """
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM events WHERE id=?", (event_id,)
                ).fetchone()
            return self._row_to_event(row) if row else None

    def list_events(self, limit: int = 100, offset: int = 0) -> list[Event]:
        """List stored events with pagination, newest first.

        Args:
            limit: Maximum number of events to return.
            offset: Number of events to skip before collecting results.

        Returns:
            The requested page of stored events.
        """
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM events ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            return [self._row_to_event(r) for r in rows]

    def update_event(self, event: Event) -> Event:
        """Replace an existing event with the supplied values.

        Args:
            event: Event carrying the new values; its identifier is the key.

        Returns:
            The updated event.

        Raises:
            KeyError: When no event with that identifier is stored.
        """
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    "UPDATE events SET name=?,event_type=?,event_date=?,guest_count=?,budget_total=?,theme=?,location=?,notes=?,updated_at=? "
                    "WHERE id=?",
                    (
                        event.name,
                        event.event_type.value
                        if hasattr(event.event_type, "value")
                        else str(event.event_type),
                        event.event_date.isoformat(),
                        event.guest_count,
                        event.budget_total,
                        event.theme,
                        event.location,
                        event.notes,
                        event.updated_at.isoformat(),
                        event.id,
                    ),
                )
                conn.commit()
                if cur.rowcount == 0:
                    raise KeyError(event.id)
            return event

    def delete_event(self, event_id: str) -> bool:
        """Delete an event and its dependent records.

        Args:
            event_id: Identifier of the event to delete.

        Returns:
            True when an event was removed, False when the identifier is unknown.
        """
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM events WHERE id=?", (event_id,))
            conn.commit()
            return cur.rowcount > 0

    def count_events(self) -> int:
        """Count the stored events.

        Returns:
            The number of events currently stored.
        """
        with self._lock, self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    # --- budget ---
    def add_budget_line(self, line: BudgetLine) -> BudgetLine:
        """Append a budget line to an event.

        Args:
            line: Budget line to store against its event.

        Returns:
            The stored budget line.
        """
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO budget_lines (id,event_id,category,allocated,spent,notes) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        line.id,
                        line.event_id,
                        line.category,
                        line.allocated,
                        line.spent,
                        line.notes,
                    ),
                )
                conn.commit()
            return line

    def list_budget(self, event_id: str) -> list[BudgetLine]:
        """List the budget lines of an event.

        Args:
            event_id: Identifier of the event whose budget is requested.

        Returns:
            The budget lines for the event, empty when it has none.
        """
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM budget_lines WHERE event_id=?", (event_id,)
                ).fetchall()
            return [
                BudgetLine(
                    id=r["id"],
                    event_id=r["event_id"],
                    category=r["category"],
                    allocated=r["allocated"],
                    spent=r["spent"],
                    notes=r["notes"],
                )
                for r in rows
            ]

    # --- timeline ---
    def add_milestone(self, m: TimelineMilestone) -> TimelineMilestone:
        """Append a timeline milestone to an event.

        Args:
            m: Milestone to store against its event.

        Returns:
            The stored milestone.
        """
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO milestones (id,event_id,title,due_date,status,notes) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        m.id,
                        m.event_id,
                        m.title,
                        m.due_date.isoformat(),
                        m.status,
                        m.notes,
                    ),
                )
                conn.commit()
            return m

    def list_timeline(self, event_id: str) -> list[TimelineMilestone]:
        """List the timeline milestones of an event in due-date order.

        Args:
            event_id: Identifier of the event whose timeline is requested.

        Returns:
            The milestones for the event, empty when it has none.
        """
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM milestones WHERE event_id=? ORDER BY due_date",
                    (event_id,),
                ).fetchall()
            return [
                TimelineMilestone(
                    id=r["id"],
                    event_id=r["event_id"],
                    title=r["title"],
                    due_date=date.fromisoformat(r["due_date"]),
                    status=r["status"],
                    notes=r["notes"],
                )
                for r in rows
            ]

    # --- vendors ---
    def add_vendor(self, v: Vendor) -> Vendor:
        """Append a vendor to an event.

        Args:
            v: Vendor to store against its event.

        Returns:
            The stored vendor.
        """
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO vendors (id,event_id,category,name,status,cost_estimate,contact,notes) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        v.id,
                        v.event_id,
                        v.category,
                        v.name,
                        v.status.value if hasattr(v.status, "value") else str(v.status),
                        v.cost_estimate,
                        v.contact,
                        v.notes,
                    ),
                )
                conn.commit()
            return v

    def list_vendors(self, event_id: str) -> list[Vendor]:
        """List the vendors of an event.

        Args:
            event_id: Identifier of the event whose vendors are requested.

        Returns:
            The vendors for the event, empty when it has none.
        """
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM vendors WHERE event_id=?", (event_id,)
                ).fetchall()
            return [self._row_to_vendor(r) for r in rows]

    def update_vendor(self, v: Vendor) -> Vendor:
        """Replace an existing vendor with the supplied values.

        Args:
            v: Vendor carrying the new values; its identifier is the key.

        Returns:
            The updated vendor.

        Raises:
            KeyError: When no vendor with that identifier is stored.
        """
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    "UPDATE vendors SET category=?,name=?,status=?,cost_estimate=?,contact=?,notes=? "
                    "WHERE id=?",
                    (
                        v.category,
                        v.name,
                        v.status.value if hasattr(v.status, "value") else str(v.status),
                        v.cost_estimate,
                        v.contact,
                        v.notes,
                        v.id,
                    ),
                )
                conn.commit()
                if cur.rowcount == 0:
                    raise KeyError(v.id)
            return v

    # --- guests ---
    def add_guest(self, g: Guest) -> Guest:
        """Append a guest to an event.

        Args:
            g: Guest to store against its event.

        Returns:
            The stored guest.
        """
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO guests (id,event_id,name,rsvp,dietary,plus_one) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        g.id,
                        g.event_id,
                        g.name,
                        g.rsvp,
                        g.dietary,
                        1 if g.plus_one else 0,
                    ),
                )
                conn.commit()
            return g

    def list_guests(self, event_id: str) -> list[Guest]:
        """List the guests of an event.

        Args:
            event_id: Identifier of the event whose guests are requested.

        Returns:
            The guests for the event, empty when it has none.
        """
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM guests WHERE event_id=?", (event_id,)
                ).fetchall()
            return [
                Guest(
                    id=r["id"],
                    event_id=r["event_id"],
                    name=r["name"],
                    rsvp=r["rsvp"],
                    dietary=r["dietary"],
                    plus_one=bool(r["plus_one"]),
                )
                for r in rows
            ]

    # --- helpers ---
    def _row_to_event(self, r: sqlite3.Row) -> Event:
        """Convert a database row into an event entity.

        Args:
            r: Row read from the ``events`` table.

        Returns:
            The corresponding event entity.
        """
        from .models import EventType

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
        from .models import VendorStatus

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
