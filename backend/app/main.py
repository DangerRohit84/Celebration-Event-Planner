"""FastAPI application: adapters + validation + rate limit + session isolation.

Adapter-only: no business logic beyond wiring. Business logic lives in
planner.py / retrieval.py / prompting.py / storage.py.
"""
from __future__ import annotations

import time
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel, Field

from .config import settings
from .security import sanitize_text, sanitize_filename, validate_pre_parse
from .storage import get_store, CapacityError, new_id
from .models import Event, EventType
from .planner import budget_breakdown, timeline_for, vendor_checklist
from .retrieval import search as retrieve_ideas
from .prompting import build_ideas_prompt, calibrate_confidence, DISCLAIMER, CANNOT_DETERMINE
from .llm import build_provider

app = FastAPI(title="Celebration & Event Planner", version="0.1.0")

# --- CORS (allowlist, never wildcard) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Demo-Session"],
)

# --- Rate limit buckets ---
_rate_buckets: dict[str, list[float]] = {}
_RATE_BUCKETS = _rate_buckets


def _rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = 60.0
    bucket = _rate_buckets.setdefault(ip, [])
    bucket[:] = [t for t in bucket if now - t < window]
    limit = settings.rate_limit_per_min
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="rate limit exceeded, slow down")
    bucket.append(now)
    # store for headers
    request.state.rate_limit_limit = limit
    request.state.rate_limit_remaining = max(0, limit - len(bucket))
    request.state.rate_limit_reset = int(now + window)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    start = time.perf_counter()
    # rate limit headers computed lazily; ensure defaults
    try:
        _rate_limit(request)
    except HTTPException as e:
        # still attach headers
        # re-raise after headers? We'll handle by storing
        request.state._rate_limited = True
        request.state._rate_exc = e
    # If rate limited, return 429 with headers
    if getattr(request.state, "_rate_limited", False):
        exc = request.state._rate_exc
        resp = JSONResponse(status_code=429, content={"detail": exc.detail})
        _attach_headers(resp, request, start, limited=True)
        return resp

    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; object-src 'none'; frame-ancestors 'none'"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Process-Time"] = f"{elapsed:.2f}ms" if False else f"{elapsed/1000:.3f}s"
    # rate limit headers
    limit = getattr(request.state, "rate_limit_limit", settings.rate_limit_per_min)
    remaining = getattr(request.state, "rate_limit_remaining", settings.rate_limit_per_min)
    reset = getattr(request.state, "rate_limit_reset", int(time.time() + 60))
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset)
    return response


def _attach_headers(resp, request, start, limited=False):
    elapsed = (time.perf_counter() - start) * 1000
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = "default-src 'self'; object-src 'none'; frame-ancestors 'none'"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Process-Time"] = f"{elapsed/1000:.3f}s"
    limit = getattr(request.state, "rate_limit_limit", settings.rate_limit_per_min)
    remaining = 0 if limited else getattr(request.state, "rate_limit_remaining", settings.rate_limit_per_min)
    reset = getattr(request.state, "rate_limit_reset", int(time.time() + 60))
    resp.headers["X-RateLimit-Limit"] = str(limit)
    resp.headers["X-RateLimit-Remaining"] = str(remaining)
    resp.headers["X-RateLimit-Reset"] = str(reset)
    if limited:
        resp.headers["Retry-After"] = "60"


# --- Pydantic schemas ---
class EventCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    event_type: str = Field("other")
    event_date: str
    guest_count: int = Field(0, ge=0, le=100000)
    budget_total: float = Field(0.0, ge=0)
    theme: str = Field("", max_length=200)
    location: str = Field("", max_length=200)
    notes: str = Field("", max_length=2000)


class EventUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    event_type: Optional[str] = Field(None, max_length=50)
    event_date: Optional[str] = Field(None, max_length=20)
    guest_count: Optional[int] = Field(None, ge=0, le=100000)
    budget_total: Optional[float] = Field(None, ge=0)
    theme: Optional[str] = Field(None, max_length=200)
    location: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = Field(None, max_length=2000)


class IdeasRequest(BaseModel):
    event_id: str
    query: str = Field(..., min_length=3, max_length=500)
    top_k: int = Field(5, ge=1, le=10)


class AskRequest(BaseModel):
    event_id: Optional[str] = None
    query: Optional[str] = None
    question: Optional[str] = None
    top_k: int = Field(5, ge=1, le=10)


class ExportRequest(BaseModel):
    event_id: str = Field(..., min_length=1, max_length=128)


# --- Helpers ---
def _parse_event_type(value: str):
    try:
        return EventType(value)
    except ValueError:
        return EventType.OTHER


# --- Routes ---
@app.get("/health")
def health():
    return {"status": "ok", "provider": settings.llm_provider}


@app.get("/", response_class=HTMLResponse)
def index():
    try:
        p = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
        if p.exists():
            return HTMLResponse(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return HTMLResponse("<h1>Celebration & Event Planner</h1>")


@app.post("/events")
def create_event(payload: EventCreate, request: Request):
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


@app.get("/events")
def list_events(request: Request, limit: int = 50, offset: int = 0):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    store = get_store()
    events = store.list_events(limit=limit, offset=offset)
    return {"events": [{"id": e.id, "name": e.name, "event_type": e.event_type.value,
                        "event_date": e.event_date.isoformat(), "guest_count": e.guest_count,
                        "budget_total": e.budget_total} for e in events]}


@app.get("/events/{event_id}")
def get_event(event_id: str, request: Request):
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


@app.put("/events/{event_id}")
def update_event(event_id: str, payload: EventUpdate, request: Request):
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
    from datetime import datetime
    ev.updated_at = datetime.utcnow()
    store.update_event(ev)
    return {"event_id": ev.id, "updated": True}


@app.delete("/events/{event_id}")
def delete_event(event_id: str, request: Request):
    store = get_store()
    if not store.delete_event(event_id):
        raise HTTPException(status_code=404, detail="not found")
    return {"deleted": True}


def _run_ideas(event_id: str, query: str, top_k: int):
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


@app.post("/ideas")
def ideas(payload: IdeasRequest, request: Request):
    return _run_ideas(payload.event_id, payload.query, payload.top_k)


@app.post("/ask")
def ask(payload: AskRequest, request: Request):
    # support both event_id+query and question
    eid = payload.event_id
    q = payload.query or payload.question
    if not eid or not q:
        raise HTTPException(status_code=422, detail="event_id and query required")
    if len(q) < 3:
        raise HTTPException(status_code=422, detail="query too short")
    return _run_ideas(eid, q, payload.top_k)


@app.post("/export")
def export_event(payload: ExportRequest, request: Request):
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


@app.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="file too large (10 MB limit)")
    filename = sanitize_filename(file.filename or "")
    try:
        validate_pre_parse(filename, file.content_type or "application/octet-stream", len(raw), raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"filename": filename, "size": len(raw), "status": "accepted"}


try:
    app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parents[2] / "frontend")), name="static")
except Exception:
    pass
