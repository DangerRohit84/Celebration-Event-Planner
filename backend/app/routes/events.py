"""Event routes: create, list, and read events."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException

from ..models import Event
from ..planner import budget_breakdown, timeline_for, vendor_checklist
from ..schemas import (
    EventCreate,
    EventCreatedResponse,
    EventDetailResponse,
    EventSummaryResponse,
)
from ..security import sanitize_text
from ..serializers import (
    budget_line_dict,
    event_detail,
    event_summary,
    milestone_dict,
    vendor_dict,
)
from ..storage import CapacityError, get_store, new_id
from .deps import STORE_FULL_RETRY_AFTER_SECONDS, _parse_event_type

router = APIRouter()


@router.post("/events", response_model=EventCreatedResponse)
def create_event(payload: EventCreate) -> dict:
    """Create a new event with budget, timeline, and vendors.
    Args:
        payload: Validated event details supplied by the client.
    Returns:
        A mapping with the new event identifier and name.
    Raises:
        HTTPException: With status 400 for invalid dates and status 429 when
            the event store is at capacity.
    """
    store = get_store()
    try:
        ev = Event(
            id=new_id(),
            name=sanitize_text(payload.name, 200),
            event_type=_parse_event_type(payload.event_type),
            event_date=date.fromisoformat(payload.event_date),
            guest_count=payload.guest_count,
            budget_total=payload.budget_total,
            theme=sanitize_text(payload.theme, 200),
            location=sanitize_text(payload.location, 200),
            notes=sanitize_text(payload.notes, 2000),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        store.create_event(ev)
    except CapacityError as e:
        raise HTTPException(
            status_code=429,
            detail="event store full",
            headers={"Retry-After": str(STORE_FULL_RETRY_AFTER_SECONDS)},
        ) from e
    for line in budget_breakdown(ev):
        store.add_budget_line(line)
    for m in timeline_for(ev):
        store.add_milestone(m)
    for v in vendor_checklist(ev):
        store.add_vendor(v)
    return {"event_id": ev.id, "name": ev.name}


@router.get("/events", response_model=EventSummaryResponse)
def list_events(limit: int = 50, offset: int = 0) -> dict:
    """List events with pagination.
    Args:
        limit: Maximum number of events to return, clamped to 1..100.
        offset: Number of events to skip before collecting results.
    Returns:
        A mapping with the requested page of event summaries.
    """
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    store = get_store()
    events = store.list_events(limit=limit, offset=offset)
    return {"events": [event_summary(e) for e in events]}


@router.get("/events/{event_id}", response_model=EventDetailResponse)
def get_event(event_id: str) -> dict:
    """Get a single event with its budget, timeline, and vendors.
    Args:
        event_id: Identifier of the event to retrieve.
    Returns:
        A mapping with the event, its budget lines, timeline, and vendors.
    Raises:
        HTTPException: With status 404 when the event does not exist.
    """
    store = get_store()
    ev = store.get_event(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="not found")
    return {
        "event": event_detail(ev),
        "budget": [budget_line_dict(b) for b in store.list_budget(event_id)],
        "timeline": [milestone_dict(m) for m in store.list_timeline(event_id)],
        "vendors": [vendor_dict(v) for v in store.list_vendors(event_id)],
    }
