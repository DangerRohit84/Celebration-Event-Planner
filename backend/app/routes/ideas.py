"""Idea and question routes grounded in the vetted corpus."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..prompting import (
    CANNOT_DETERMINE,
    DISCLAIMER,
    build_ideas_prompt,
    calibrate_confidence,
)
from ..retrieval import search as retrieve_ideas
from ..schemas import AskRequest, IdeasRequest, IdeasResponse
from ..serializers import citation_dicts, idea_texts
from ..storage import get_store
from .answering import _document_context, _generate_answer

router = APIRouter()


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
