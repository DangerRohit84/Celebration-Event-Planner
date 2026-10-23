"""Event serializers: domain objects -> JSON-ready dictionaries.

The HTTP layer stays a thin Interface Adapter: handlers parse the request,
call the domain, and hand the domain result to a serializer. No handler
builds response payloads with inline dict comprehensions.

Every function here is pure (no I/O, no globals) and fully documented so the
wire format of each endpoint is described in exactly one place.
"""

from __future__ import annotations

from .models import BudgetLine, Event, TimelineMilestone, Vendor


def event_summary(ev: Event) -> dict:
    """Serialize an event as a list-view summary.

    Args:
        ev: Domain event to serialize.

    Returns:
        A mapping with the event identifier, name, type, date, guest count,
        and total budget.
    """
    return {
        "id": ev.id,
        "name": ev.name,
        "event_type": ev.event_type.value,
        "event_date": ev.event_date.isoformat(),
        "guest_count": ev.guest_count,
        "budget_total": ev.budget_total,
    }


def event_detail(ev: Event) -> dict:
    """Serialize an event as a full detail view.

    Args:
        ev: Domain event to serialize.

    Returns:
        A mapping with the summary fields plus theme, location, and notes.
    """
    return {
        "id": ev.id,
        "name": ev.name,
        "event_type": ev.event_type.value,
        "event_date": ev.event_date.isoformat(),
        "guest_count": ev.guest_count,
        "budget_total": ev.budget_total,
        "theme": ev.theme,
        "location": ev.location,
        "notes": ev.notes,
    }


def budget_line_dict(b: BudgetLine) -> dict:
    """Serialize a budget line.

    Args:
        b: Domain budget line to serialize.

    Returns:
        A mapping with the line identifier, category, allocation, and spend.
    """
    return {
        "id": b.id,
        "category": b.category,
        "allocated": b.allocated,
        "spent": b.spent,
    }


def milestone_dict(m: TimelineMilestone) -> dict:
    """Serialize a timeline milestone.

    Args:
        m: Domain milestone to serialize.

    Returns:
        A mapping with the milestone identifier, title, due date, and status.
    """
    return {
        "id": m.id,
        "title": m.title,
        "due_date": m.due_date.isoformat(),
        "status": m.status,
    }


def vendor_dict(v: Vendor) -> dict:
    """Serialize a vendor checklist entry.

    Args:
        v: Domain vendor to serialize.

    Returns:
        A mapping with the vendor identifier, category, name, status, and
        cost estimate.
    """
    return {
        "id": v.id,
        "category": v.category,
        "name": v.name,
        "status": v.status.value,
        "cost_estimate": v.cost_estimate,
    }
