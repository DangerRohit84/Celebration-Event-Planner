"""SQLite backend: event lifecycle operations."""

from __future__ import annotations

from ..models import Event
from .protocol import CapacityError
from .sqlite_base import SQLiteBase


class SQLiteEvents(SQLiteBase):
    """Event CRUD against the ``events`` table."""

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
