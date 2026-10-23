"""Storage interface: shared identifiers, capacity error, repository contract."""

from __future__ import annotations

import uuid
from typing import Protocol

from ..models import BudgetLine, Event, TimelineMilestone, Vendor


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
