"""SQLite backend: budget line and timeline milestone operations."""

from __future__ import annotations

from datetime import date

from ..models import BudgetLine, TimelineMilestone
from .sqlite_base import SQLiteBase


class SQLiteBudget(SQLiteBase):
    """Budget and milestone persistence against their tables."""

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
