"""Export route: download an event plan."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas import ExportRequest, ExportResponse
from ..serializers import event_plan_dict
from ..storage import get_store

router = APIRouter()


@router.post("/export", response_model=ExportResponse)
def export_event(payload: ExportRequest) -> dict:
    """Export an event plan.
    Args:
        payload: Validated export request carrying the event identifier.
    Returns:
        A mapping with the event, its budget, timeline, vendors, and disclaimer.
    Raises:
        HTTPException: With status 404 when the event does not exist.
    """
    eid = payload.event_id
    store = get_store()
    ev = store.get_event(eid)
    if not ev:
        raise HTTPException(status_code=404, detail="not found")
    return event_plan_dict(
        ev,
        store.list_budget(eid),
        store.list_timeline(eid),
        store.list_vendors(eid),
    )
