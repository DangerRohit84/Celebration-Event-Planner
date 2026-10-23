"""Export serializer: a complete event plan -> the export wire format.

The export payload intentionally omits the per-row identifiers used by the
interactive detail endpoint so the exported document stays stable and
self-describing. Pure function, no I/O.
"""

from __future__ import annotations

from .event_serializers import event_detail
from .models import BudgetLine, Event, TimelineMilestone, Vendor
from .prompting import DISCLAIMER


def event_plan_dict(
    ev: Event,
    budget: list[BudgetLine],
    timeline: list[TimelineMilestone],
    vendors: list[Vendor],
) -> dict:
    """Serialize a complete, exportable event plan.

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
