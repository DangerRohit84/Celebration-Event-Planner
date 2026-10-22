"""Pure serializers: domain objects -> JSON-ready dictionaries.

The HTTP layer stays a thin Interface Adapter: handlers parse the request,
call the domain, and hand the domain result to a serializer. No handler
builds response payloads with inline dict comprehensions.

Every function here is pure (no I/O, no globals) and fully documented so the
wire format of each endpoint is described in exactly one place.
"""

from __future__ import annotations

from .models import BudgetLine, Event, TimelineMilestone, Vendor
from .prompting import DISCLAIMER


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


def citation_dict(hit: dict) -> dict:
    """Serialize a retrieved corpus entry as a citation.

    Args:
        hit: Retrieved corpus entry carrying "id", "text", and "score".

    Returns:
        A mapping with the source identifier, the quoted text, and the
        similarity score.
    """
    return {
        "id": str(hit.get("id") or ""),
        "text": str(hit.get("text") or ""),
        "score": float(hit.get("score") or 0.0),
    }


def citation_dicts(hits: list[dict]) -> list[dict]:
    """Serialize retrieved corpus entries as a list of citations.

    Args:
        hits: Retrieved corpus entries backing the answer.

    Returns:
        One citation mapping per retrieved entry, in retrieval order.
    """
    return [citation_dict(hit) for hit in hits]


def idea_texts(hits: list[dict]) -> list[str]:
    """Serialize retrieved corpus entries as a list of idea strings.

    Args:
        hits: Retrieved corpus entries backing the answer.

    Returns:
        The text of every retrieved entry, in retrieval order.
    """
    return [str(hit.get("text") or "") for hit in hits]


def event_plan_dict(
    ev: Event,
    budget: list[BudgetLine],
    timeline: list[TimelineMilestone],
    vendors: list[Vendor],
) -> dict:
    """Serialize a complete, exportable event plan.

    The export payload intentionally omits the per-row identifiers used by
    the interactive detail endpoint so the exported document stays stable
    and self-describing.

    Args:
        ev: Domain event being exported.
        budget: Budget lines belonging to the event.
        timeline: Milestones belonging to the event.
        vendors: Vendor checklist entries belonging to the event.

    Returns:
        A mapping with the event, its budget, timeline, vendors, and the
        standing disclaimer.
    """
    return {
        "event": event_detail(ev),
        "budget": [
            {"category": b.category, "allocated": b.allocated, "spent": b.spent}
            for b in budget
        ],
        "timeline": [
            {
                "title": m.title,
                "due_date": m.due_date.isoformat(),
                "status": m.status,
            }
            for m in timeline
        ],
        "vendors": [
            {
                "category": v.category,
                "name": v.name,
                "status": v.status.value,
                "cost_estimate": v.cost_estimate,
            }
            for v in vendors
        ],
        "disclaimer": DISCLAIMER,
    }
