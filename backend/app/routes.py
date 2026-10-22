"""API routes for the Celebration & Event Planner."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse

from .config import settings
from .llm import build_provider
from .models import Event, EventType
from .planner import budget_breakdown, timeline_for, vendor_checklist
from .prompting import (
    CANNOT_DETERMINE,
    DISCLAIMER,
    build_ideas_prompt,
    calibrate_confidence,
)
from .retrieval import search as retrieve_ideas
from .schemas import AskRequest, EventCreate, EventUpdate, ExportRequest, IdeasRequest
from .security import sanitize_filename, sanitize_text, validate_pre_parse
from .storage import CapacityError, get_store, new_id

router = APIRouter()


def _parse_event_type(value: str) -> EventType:
    """Parse an event type string, defaulting to OTHER."""
    try:
        return EventType(value)
    except ValueError:
        return EventType.OTHER


@router.get("/health")
def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "provider": settings.llm_provider}


@router.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Serve the frontend index page, falling back to a minimal page."""
    p = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    try:
        if p.exists():
            return HTMLResponse(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        pass
    return HTMLResponse("<h1>Celebration & Event Planner</h1>")


@router.post("/events")
def create_event(payload: EventCreate, request: Request) -> dict:
    """Create a new event with budget, timeline, and vendors."""
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
        raise HTTPException(status_code=400, detail=str(e))
    try:
        store.create_event(ev)
    except CapacityError:
        raise HTTPException(status_code=429, detail="event store full")
    for line in budget_breakdown(ev):
        store.add_budget_line(line)
    for m in timeline_for(ev):
        store.add_milestone(m)
    for v in vendor_checklist(ev):
        store.add_vendor(v)
    return {"event_id": ev.id, "name": ev.name}


@router.get("/events")
def list_events(request: Request, limit: int = 50, offset: int = 0) -> dict:
    """List events with pagination."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    store = get_store()
    events = store.list_events(limit=limit, offset=offset)
    return {"events": [{"id": e.id, "name": e.name, "event_type": e.event_type.value,
                        "event_date": e.event_date.isoformat(), "guest_count": e.guest_count,
                        "budget_total": e.budget_total} for e in events]}


@router.get("/events/{event_id}")
def get_event(event_id: str, request: Request) -> dict:
    """Get a single event with its budget, timeline, and vendors."""
    store = get_store()
    ev = store.get_event(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="not found")
    return {
        "event": {"id": ev.id, "name": ev.name, "event_type": ev.event_type.value,
                  "event_date": ev.event_date.isoformat(), "guest_count": ev.guest_count,
                  "budget_total": ev.budget_total, "theme": ev.theme, "location": ev.location, "notes": ev.notes},
        "budget": [{"id": b.id, "category": b.category, "allocated": b.allocated, "spent": b.spent} for b in store.list_budget(event_id)],
        "timeline": [{"id": m.id, "title": m.title, "due_date": m.due_date.isoformat(), "status": m.status} for m in store.list_timeline(event_id)],
        "vendors": [{"id": v.id, "category": v.category, "name": v.name, "status": v.status.value, "cost_estimate": v.cost_estimate} for v in store.list_vendors(event_id)],
    }


@router.put("/events/{event_id}")
def update_event(event_id: str, payload: EventUpdate, request: Request) -> dict:
    """Update an existing event."""
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
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid date")
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


@router.delete("/events/{event_id}")
def delete_event(event_id: str, request: Request) -> dict:
    """Delete an event."""
    store = get_store()
    if not store.delete_event(event_id):
        raise HTTPException(status_code=404, detail="not found")
    return {"deleted": True}


def _run_ideas(event_id: str, query: str, top_k: int) -> dict:
    """Run idea generation for an event."""
    store = get_store()
    ev = store.get_event(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="not found")
    et = ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type)
    hits = retrieve_ideas(query, top_k=top_k, event_type=et)
    if not hits:
        return {"ideas": [], "confidence": "Cannot Determine",
                "citations": [], "disclaimer": DISCLAIMER,
                "answer": CANNOT_DETERMINE, "ideas_text": CANNOT_DETERMINE}
    prompt = build_ideas_prompt(query, hits, et)
    provider = build_provider()
    text = provider.answer(prompt)
    conf = calibrate_confidence(hits)
    cites = [{"id": h.get("id"), "text": h.get("text"), "score": h.get("score")} for h in hits]
    return {
        "ideas_text": text,
        "ideas": [h.get("text") for h in hits],
        "confidence": conf,
        "citations": cites,
        "disclaimer": DISCLAIMER,
        "answer": text,
    }


@router.post("/ideas")
def ideas(payload: IdeasRequest, request: Request) -> dict:
    """Generate ideas for an event."""
    return _run_ideas(payload.event_id, payload.query, payload.top_k)


@router.post("/ask")
def ask(payload: AskRequest, request: Request) -> dict:
    """Ask a planning question for an event."""
    eid = payload.event_id
    q = payload.query or payload.question
    if not eid or not q:
        raise HTTPException(status_code=422, detail="event_id and query required")
    if len(q) < 3:
        raise HTTPException(status_code=422, detail="query too short")
    return _run_ideas(eid, q, payload.top_k)


@router.post("/export")
def export_event(payload: ExportRequest, request: Request) -> dict:
    """Export an event plan."""
    eid = payload.event_id
    store = get_store()
    ev = store.get_event(eid)
    if not ev:
        raise HTTPException(status_code=404, detail="not found")
    data = {
        "event": {"id": ev.id, "name": ev.name, "event_type": ev.event_type.value,
                  "event_date": ev.event_date.isoformat(), "guest_count": ev.guest_count,
                  "budget_total": ev.budget_total, "theme": ev.theme, "location": ev.location, "notes": ev.notes},
        "budget": [{"category": b.category, "allocated": b.allocated, "spent": b.spent} for b in store.list_budget(eid)],
        "timeline": [{"title": m.title, "due_date": m.due_date.isoformat(), "status": m.status} for m in store.list_timeline(eid)],
        "vendors": [{"category": v.category, "name": v.name, "status": v.status.value, "cost_estimate": v.cost_estimate} for v in store.list_vendors(eid)],
        "disclaimer": DISCLAIMER,
    }
    return data


@router.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)):  # noqa: B008
    """Upload a PDF document."""
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="file too large (10 MB limit)")
    filename = sanitize_filename(file.filename or "")
    try:
        validate_pre_parse(filename, file.content_type or "application/octet-stream", len(raw), raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"filename": filename, "size": len(raw), "status": "accepted"}
