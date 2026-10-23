"""In-memory event store: bounded, thread-safe event lifecycle operations."""

from __future__ import annotations

import threading

from ..config import settings
from ..models import BudgetLine, Event, TimelineMilestone, Vendor
from .memory_records import _MemoryRecords
from .protocol import CapacityError


class _MemoryBase:
    """Shared in-memory state plus the event lifecycle operations."""

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
        """
        with self._lock:
            self._guard_capacity()
            self._events[event.id] = event
            self._budget[event.id] = []
            self._timeline[event.id] = []
            self._vendors[event.id] = []
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
            return True

    def count_events(self) -> int:
        """Count the stored events.
        Returns:
            The number of events currently stored.
        """
        with self._lock:
            return len(self._events)


class InMemoryStore(_MemoryRecords, _MemoryBase):
    """In-memory event store (tests + ephemeral)."""
