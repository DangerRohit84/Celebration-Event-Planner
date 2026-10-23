"""System routes: health check and the frontend index page."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from ..config import settings
from ..schemas import HealthResponse

router = APIRouter()


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
    p = Path(__file__).resolve().parents[3] / "frontend" / "index.html"
    try:
        if p.exists():
            return HTMLResponse(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        pass
    return HTMLResponse("<h1>Celebration & Event Planner</h1>")
