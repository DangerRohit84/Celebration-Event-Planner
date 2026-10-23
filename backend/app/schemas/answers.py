"""Pydantic answer schemas: grounded ideas, exports, and uploads."""

from __future__ import annotations

from pydantic import BaseModel

from .events import EventDetail, ExportBudgetLine, ExportMilestone, ExportVendor


class Citation(BaseModel):
    """A single grounded source backing a generated idea."""

    id: str = ""
    text: str = ""
    score: float = 0.0


class IdeasResponse(BaseModel):
    """Grounded idea generation result."""

    ideas_text: str
    ideas: list[str]
    confidence: str
    citations: list[Citation]
    disclaimer: str
    answer: str
    plain_language: bool = False


class ExportResponse(BaseModel):
    """The exportable event plan."""

    event: EventDetail
    budget: list[ExportBudgetLine]
    timeline: list[ExportMilestone]
    vendors: list[ExportVendor]
    disclaimer: str


class UploadResponse(BaseModel):
    """Result of an accepted document upload."""

    filename: str
    size: int
    status: str
    upload_id: str = ""
    pages: int = 0
    chunks: int = 0
