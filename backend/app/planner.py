"""Planning engine: budget breakdown, timeline, vendor checklist generation.

Pure functions (no I/O, no LLM). Deterministic given inputs.
LLM is used only for personalized ideas (see prompting.py).

The allocation tables, vendor categories, and milestone offsets live in
:mod:`backend.app.planner_templates` and are re-exported here so the
historical import path keeps working.
"""

from __future__ import annotations

from datetime import date, timedelta

from .models import BudgetLine, Event, TimelineMilestone, Vendor
from .planner_templates import BUDGET_TEMPLATES as BUDGET_TEMPLATES
from .planner_templates import MILESTONE_OFFSETS as MILESTONE_OFFSETS
from .planner_templates import VENDOR_CATEGORIES as VENDOR_CATEGORIES
from .storage import new_id


def budget_breakdown(event: Event) -> list[BudgetLine]:
    """Generate a budget breakdown for an event using its template.

    Args:
        event: Event whose total budget and type drive the allocation.

    Returns:
        One budget line per template category, with allocated amounts rounded
        to two decimals.
    """
    template = BUDGET_TEMPLATES.get(
        event.event_type.value
        if hasattr(event.event_type, "value")
        else str(event.event_type),
        BUDGET_TEMPLATES["other"],
    )
    lines: list[BudgetLine] = []
    for category, pct in template:
        lines.append(
            BudgetLine(
                id=new_id(),
                event_id=event.id,
                category=category,
                allocated=round(event.budget_total * pct, 2),
            )
        )
    return lines


def timeline_for(event: Event) -> list[TimelineMilestone]:
    """Generate a planning timeline for an event.

    Args:
        event: Event whose date anchors the milestone due dates.

    Returns:
        The milestones sorted by due date; past-dated milestones are clamped
        to today.
    """
    milestones: list[TimelineMilestone] = []
    for offset, title in MILESTONE_OFFSETS:
        due = event.event_date - timedelta(days=offset)
        due = max(due, date.today())
        milestones.append(
            TimelineMilestone(
                id=new_id(),
                event_id=event.id,
                title=title,
                due_date=due,
            )
        )
    # sort by due_date ascending
    milestones.sort(key=lambda m: m.due_date)
    return milestones


def vendor_checklist(event: Event) -> list[Vendor]:
    """Generate a vendor checklist for an event.

    Args:
        event: Event whose type selects the vendor categories.

    Returns:
        One unbooked vendor entry per category in the event type's checklist.
    """
    et = (
        event.event_type.value
        if hasattr(event.event_type, "value")
        else str(event.event_type)
    )
    cats = VENDOR_CATEGORIES.get(et, VENDOR_CATEGORIES["other"])
    return [Vendor(id=new_id(), event_id=event.id, category=c) for c in cats]


def total_allocated(lines: list[BudgetLine]) -> float:
    """Return the total allocated budget across lines.

    Args:
        lines: Budget lines to sum.

    Returns:
        The sum of the allocated amounts, rounded to two decimals.
    """
    return round(sum(line.allocated for line in lines), 2)
