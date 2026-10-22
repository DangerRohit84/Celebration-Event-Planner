"""API routes for the Celebration & Event Planner.

Thin Interface Adapters: each handler parses the request, calls the domain,
and returns the domain result through a serializer. All business rules live
in planner.py / retrieval.py / prompting.py / storage.py.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from .config import settings
from .ingest import (
    DocumentCapacityError,
    DocumentError,
    get_document_store,
    parse_pdf,
    relevant_chunks,
)
from .llm import build_provider
from .models import Event, EventType
from .planner import budget_breakdown, timeline_for, vendor_checklist
from .prompting import (
    CANNOT_DETERMINE,
    DISCLAIMER,
    build_ideas_prompt,
    calibrate_confidence,
    render_grounded_ideas,
)
from .retrieval import search as retrieve_ideas
from .schemas import (
    AskRequest,
    EventCreate,
    EventCreatedResponse,
    EventDeletedResponse,
    EventDetailResponse,
    EventSummaryResponse,
    EventUpdate,
    EventUpdatedResponse,
    ExportRequest,
    ExportResponse,
    HealthResponse,
    IdeasRequest,
    IdeasResponse,
    UploadResponse,
)
from .security import sanitize_filename, sanitize_text, validate_pre_parse
from .serializers import (
    budget_line_dict,
    citation_dicts,
    event_detail,
    event_plan_dict,
    event_summary,
    idea_texts,
    milestone_dict,
    vendor_dict,
)
from .storage import CapacityError, get_store, new_id

logger = logging.getLogger(__name__)

router = APIRouter()

# Retry-After written when the bounded event store is full.
STORE_FULL_RETRY_AFTER_SECONDS = 30
# Retry-After written when the bounded session document store is full.
DOCUMENT_STORE_FULL_RETRY_AFTER_SECONDS = 30


def _parse_event_type(value: str) -> EventType:
    """Parse an event type string, defaulting to OTHER.

    Args:
        value: Raw event type identifier from the client.

    Returns:
        The matching event type, or EventType.OTHER for unknown values.
    """
    try:
        return EventType(value)
    except ValueError:
        return EventType.OTHER


@router.get("/health", response_model=HealthResponse)
def health() -> dict:
    """Health check endpoint.

    Returns:
        A mapping with the service status and the active LLM provider.
    """
    return {"status": "ok", "provider": settings.llm_provider}


@router.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Serve the frontend index page, falling back to a minimal page.

    Returns:
        The frontend HTML, or a minimal placeholder page when it is unreadable.
    """
    p = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    try:
        if p.exists():
            return HTMLResponse(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        pass
    return HTMLResponse("<h1>Celebration & Event Planner</h1>")


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


def _generate_answer(
    prompt: str, hits: list[dict], plain_language: bool = False,
) -> str:
    """Answer a grounded prompt, degrading safely when the provider fails.

    A provider outage (network timeout, upstream API error, missing SDK) must
    never turn into a 500 or leak a stack trace. The failure is logged with
    the exception class only - no secrets and no user input - and the request
    falls back to the deterministic echo provider, then to an inline grounded
    rendering of the retrieved corpus entries.

    Args:
        prompt: Fully rendered prompt to send to the provider.
        hits: Retrieved corpus entries backing the grounded fallback.
        plain_language: When True, the provider is asked for short,
            jargon-free sentences.

    Returns:
        The provider's answer, or a deterministic grounded answer derived from
        the retrieved hits.
    """
    try:
        return build_provider().answer(prompt, plain_language=plain_language)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "LLM provider '%s' failed (%s); degrading to the echo provider",
            settings.llm_provider,
            type(exc).__name__,
        )
    try:
        return build_provider("echo").answer(prompt, plain_language=plain_language)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Echo provider failed (%s); using the inline grounded fallback",
            type(exc).__name__,
        )
    return render_grounded_ideas(hits, plain_language=plain_language)


def _document_context(query: str) -> list[str]:
    """Return excerpts from the session document that match the query.

    The most recently uploaded document acts as the session document. Its
    chunks are ranked by term overlap with the query and the best few are
    injected into the prompt as additional background.

    Args:
        query: The user's question.

    Returns:
        The matching chunk texts, or an empty list when no document has been
        uploaded or nothing in it matches the query.
    """
    document = get_document_store().latest()
    if document is None:
        return []
    return relevant_chunks(document, query)


def _run_ideas(
    event_id: str, query: str, top_k: int, plain_language: bool = False,
) -> dict:
    """Run idea generation for an event.

    Args:
        event_id: Identifier of the event the ideas belong to.
        query: User question to ground the ideas in.
        top_k: Maximum number of corpus entries to retrieve.
        plain_language: When True, the answer is written in short,
            jargon-free sentences.

    Returns:
        A mapping with the ideas, their confidence label, citations, the
        disclaimer, and whether plain language was used; a "Cannot Determine"
        payload when nothing was retrieved.

    Raises:
        HTTPException: With status 404 when the event does not exist.
    """
    store = get_store()
    ev = store.get_event(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="not found")
    et = ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type)
    hits = retrieve_ideas(query, top_k=top_k, event_type=et)
    if not hits:
        return {
            "ideas": [],
            "confidence": "Cannot Determine",
            "citations": [],
            "disclaimer": DISCLAIMER,
            "answer": CANNOT_DETERMINE,
            "ideas_text": CANNOT_DETERMINE,
            "plain_language": plain_language,
        }
    prompt = build_ideas_prompt(
        query,
        hits,
        et,
        plain_language=plain_language,
        document_chunks=_document_context(query),
    )
    text = _generate_answer(prompt, hits, plain_language=plain_language)
    conf = calibrate_confidence(hits)
    return {
        "ideas_text": text,
        "ideas": idea_texts(hits),
        "confidence": conf,
        "citations": citation_dicts(hits),
        "disclaimer": DISCLAIMER,
        "answer": text,
        "plain_language": plain_language,
    }


@router.post("/ideas", response_model=IdeasResponse)
def ideas(payload: IdeasRequest) -> dict:
    """Generate ideas for an event.

    Args:
        payload: Validated idea request carrying the event, query, and top_k.

    Returns:
        A mapping with the ideas, confidence, citations, and disclaimer.

    Raises:
        HTTPException: With status 404 when the event does not exist.
    """
    return _run_ideas(
        payload.event_id, payload.query, payload.top_k, payload.plain_language,
    )


@router.post("/ask", response_model=IdeasResponse)
def ask(payload: AskRequest) -> dict:
    """Ask a planning question for an event.

    Args:
        payload: Validated question carrying the event id, query, and top_k.

    Returns:
        A mapping with the ideas, confidence, citations, and disclaimer.

    Raises:
        HTTPException: With status 422 for a missing or too-short query and
            status 404 when the event does not exist.
    """
    eid = payload.event_id
    q = payload.query or payload.question
    if not eid or not q:
        raise HTTPException(status_code=422, detail="event_id and query required")
    if len(q) < 3:
        raise HTTPException(status_code=422, detail="query too short")
    return _run_ideas(eid, q, payload.top_k, payload.plain_language)


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


@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> dict:  # noqa: B008
    """Upload and parse a PDF document.

    The upload is validated before it is parsed (extension, bounded read,
    magic bytes, content type), then the PDF is opened with ``pypdf`` to
    count its pages and extract its text. The extracted text is split into
    section-aware chunks that are kept for the session, so a later question
    can be grounded in the uploaded document as well as in the vetted corpus.

    The session document store is bounded by the ``MAX_DOCUMENTS`` setting:
    when it is saturated the upload is refused with a 429 instead of
    silently dropping an earlier document.

    Args:
        file: Uploaded PDF payload, read with a bounded buffer.

    Returns:
        A mapping with the sanitized filename, size, acceptance status, the
        upload identifier, the page count, and the number of chunks kept.

    Raises:
        HTTPException: With status 413 when the file exceeds the size limit,
            status 400 when it fails PDF pre-parse validation or cannot be
            parsed (for example a scanned, image-only document), and status
            429 when the session document store is saturated.
    """
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="file too large (10 MB limit)")
    filename = sanitize_filename(file.filename or "")
    content_type = file.content_type or "application/octet-stream"
    try:
        validate_pre_parse(filename, content_type, len(raw), raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        document = parse_pdf(raw, filename)
    except DocumentError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        get_document_store().add(document)
    except DocumentCapacityError as e:
        raise HTTPException(
            status_code=429,
            detail="document store full",
            headers={"Retry-After": str(DOCUMENT_STORE_FULL_RETRY_AFTER_SECONDS)},
        ) from e
    return {
        "filename": filename,
        "size": len(raw),
        "status": "accepted",
        "upload_id": document.document_id,
        "pages": document.pages,
        "chunks": len(document.chunks),
    }
