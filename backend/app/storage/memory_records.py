"""In-memory child records: budget lines, milestones, and vendors."""

from __future__ import annotations

import threading

from ..models import BudgetLine, TimelineMilestone, Vendor


class _MemoryRecords:
    """Child-record operations attached to in-memory events."""

    _lock: threading.Lock
    _budget: dict[str, list[BudgetLine]]
    _timeline: dict[str, list[TimelineMilestone]]
    _vendors: dict[str, list[Vendor]]

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
