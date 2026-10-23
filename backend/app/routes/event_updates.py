"""Event routes: update and delete events."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException

from ..schemas import EventDeletedResponse, EventUpdate, EventUpdatedResponse
from ..security import sanitize_text
from ..storage import get_store
from .deps import _parse_event_type

router = APIRouter()


@router.put("/events/{event_id}", response_model=EventUpdatedResponse)
def update_event(event_id: str, payload: EventUpdate) -> dict:
    """Update an existing event.
    Args:
        event_id: Identifier of the event to update.
        payload: Validated fields to apply; omitted fields are left unchanged.
    Returns:
        A mapping with the event identifier and an update confirmation.
    Raises:
        HTTPException: With status 404 when the event does not exist and
            status 400 for an unparsable date.
    """
    store = get_store()
    ev = store.get_event(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="not found")
    if payload.name is not None:
        ev.name = sanitize_text(payload.name, 200)
    if payload.event_type is not None:
        ev.event_type = _parse_event_type(payload.event_type)
    if payload.event_date is not None:
        try:
            ev.event_date = date.fromisoformat(payload.event_date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="invalid date") from e
    if payload.guest_count is not None:
        ev.guest_count = payload.guest_count
    if payload.budget_total is not None:
        ev.budget_total = payload.budget_total
    if payload.theme is not None:
        ev.theme = sanitize_text(payload.theme, 200)
    if payload.location is not None:
        ev.location = sanitize_text(payload.location, 200)
    if payload.notes is not None:
        ev.notes = sanitize_text(payload.notes, 2000)
    ev.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)  # noqa: UP017
    store.update_event(ev)
    return {"event_id": ev.id, "updated": True}


@router.delete("/events/{event_id}", response_model=EventDeletedResponse)
def delete_event(event_id: str) -> dict:
    """Delete an event.
    Args:
        event_id: Identifier of the event to delete.
    Returns:
        A mapping confirming the deletion.
    Raises:
        HTTPException: With status 404 when the event does not exist.
    """
    store = get_store()
    if not store.delete_event(event_id):
        raise HTTPException(status_code=404, detail="not found")
    return {"deleted": True}
