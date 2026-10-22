"""Planning engine: budget breakdown, timeline, vendor checklist generation.

Pure functions (no I/O, no LLM). Deterministic given inputs.
LLM is used only for personalized ideas (see prompting.py).
"""

from __future__ import annotations

from datetime import date, timedelta

from .models import BudgetLine, Event, TimelineMilestone, Vendor
from .storage import new_id

# Default budget allocation percentages by event type.
BUDGET_TEMPLATES: dict[str, list[tuple[str, float]]] = {
    "wedding": [
        ("venue", 0.30),
        ("catering", 0.25),
        ("decor", 0.12),
        ("photography", 0.10),
        ("attire", 0.08),
        ("music", 0.06),
        ("invitations", 0.03),
        ("transport", 0.03),
        ("contingency", 0.03),
    ],
    "birthday": [
        ("venue", 0.20),
        ("catering", 0.30),
        ("decor", 0.15),
        ("cake", 0.10),
        ("entertainment", 0.12),
        ("invitations", 0.05),
        ("gifts", 0.05),
        ("contingency", 0.03),
    ],
    "community": [
        ("venue", 0.25),
        ("catering", 0.20),
        ("decor", 0.10),
        ("sound_av", 0.12),
        ("permits", 0.08),
        ("marketing", 0.08),
        ("volunteers", 0.05),
        ("contingency", 0.12),
    ],
    "corporate": [
        ("venue", 0.25),
        ("catering", 0.20),
        ("av", 0.15),
        ("decor", 0.08),
        ("speakers", 0.12),
        ("marketing", 0.08),
        ("swag", 0.07),
        ("contingency", 0.05),
    ],
    "other": [
        ("venue", 0.30),
        ("catering", 0.25),
        ("decor", 0.15),
        ("misc", 0.20),
        ("contingency", 0.10),
    ],
}

VENDOR_CATEGORIES: dict[str, list[str]] = {
    "wedding": [
        "venue",
        "caterer",
        "decorator",
        "photographer",
        "videographer",
        "dj_band",
        "florist",
        "makeup",
        "transport",
        "cake",
    ],
    "birthday": [
        "venue",
        "caterer",
        "decorator",
        "entertainer",
        "cake",
        "photographer",
    ],
    "community": ["venue", "caterer", "sound_av", "permits", "marketing", "volunteers"],
    "corporate": [
        "venue",
        "caterer",
        "av",
        "decorator",
        "speakers",
        "marketing",
        "swag",
    ],
    "other": ["venue", "caterer", "decorator"],
}

# Milestone offsets (days before event) -> title
MILESTONE_OFFSETS: list[tuple[int, str]] = [
    (180, "Set budget and guest list"),
    (120, "Book venue"),
    (90, "Book caterer and key vendors"),
    (60, "Send invitations"),
    (30, "Finalize menu and decor"),
    (14, "Confirm RSVPs and headcount"),
    (7, "Final vendor confirmations"),
    (1, "Day-before checklist"),
    (0, "Event day"),
]


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
