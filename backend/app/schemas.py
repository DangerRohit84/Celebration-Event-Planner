"""Pydantic request/response schemas for the API.

Request schemas describe what the client may send; response schemas describe
the exact wire format the server returns. Both live here so the public API
contract is defined in a single place and can be published as OpenAPI.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    """Schema for creating an event."""

    name: str = Field(..., min_length=1, max_length=200)
    event_type: str = Field("other")
    event_date: str
    guest_count: int = Field(0, ge=0, le=100000)
    budget_total: float = Field(0.0, ge=0)
    theme: str = Field("", max_length=200)
    location: str = Field("", max_length=200)
    notes: str = Field("", max_length=2000)


class EventUpdate(BaseModel):
    """Schema for updating an event."""

    name: str | None = Field(None, min_length=1, max_length=200)
    event_type: str | None = Field(None, max_length=50)
    event_date: str | None = Field(None, max_length=20)
    guest_count: int | None = Field(None, ge=0, le=100000)
    budget_total: float | None = Field(None, ge=0)
    theme: str | None = Field(None, max_length=200)
    location: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=2000)


class IdeasRequest(BaseModel):
    """Schema for an ideas request."""

    event_id: str
    query: str = Field(..., min_length=3, max_length=500)
    top_k: int = Field(5, ge=1, le=10)


class AskRequest(BaseModel):
    """Schema for an ask request."""

    event_id: str | None = None
    query: str | None = None
    question: str | None = None
    top_k: int = Field(5, ge=1, le=10)


class ExportRequest(BaseModel):
    """Schema for an export request."""

    event_id: str = Field(..., min_length=1, max_length=128)


# --------------------------------------------------------------------------
# Response schemas - these define the exact JSON wire format.
# --------------------------------------------------------------------------


class Citation(BaseModel):
    """A single grounded source backing a generated idea."""

    id: str = ""
    text: str = ""
    score: float = 0.0


class EventSummary(BaseModel):
    """Compact event projection used by the event list endpoint."""

    id: str
    name: str
    event_type: str
    event_date: str
    guest_count: int
    budget_total: float


class EventDetail(BaseModel):
    """Full event projection used by the event detail and export endpoints."""

    id: str
    name: str
    event_type: str
    event_date: str
    guest_count: int
    budget_total: float
    theme: str = ""
    location: str = ""
    notes: str = ""


class BudgetLineResponse(BaseModel):
    """A budget allocation line belonging to an event."""

    id: str
    category: str
    allocated: float
    spent: float


class MilestoneResponse(BaseModel):
    """A planning milestone belonging to an event."""

    id: str
    title: str
    due_date: str
    status: str


class VendorResponse(BaseModel):
    """A vendor checklist entry belonging to an event."""

    id: str
    category: str
    name: str
    status: str
    cost_estimate: float


class ExportBudgetLine(BaseModel):
    """Budget line projection used by the export document."""

    category: str
    allocated: float
    spent: float


class ExportMilestone(BaseModel):
    """Milestone projection used by the export document."""

    title: str
    due_date: str
    status: str


class ExportVendor(BaseModel):
    """Vendor projection used by the export document."""

    category: str
    name: str
    status: str
    cost_estimate: float


class HealthResponse(BaseModel):
    """Service liveness and active LLM provider."""

    status: str
    provider: str


class EventCreatedResponse(BaseModel):
    """Acknowledgement returned when an event is created."""

    event_id: str
    name: str


class EventUpdatedResponse(BaseModel):
    """Acknowledgement returned when an event is updated."""

    event_id: str
    updated: bool


class EventDeletedResponse(BaseModel):
    """Acknowledgement returned when an event is deleted."""

    deleted: bool


class EventSummaryResponse(BaseModel):
    """A page of event summaries."""

    events: list[EventSummary]


class EventDetailResponse(BaseModel):
    """An event together with its budget, timeline, and vendors."""

    event: EventDetail
    budget: list[BudgetLineResponse]
    timeline: list[MilestoneResponse]
    vendors: list[VendorResponse]


class IdeasResponse(BaseModel):
    """Grounded idea generation result."""

    ideas_text: str
    ideas: list[str]
    confidence: str
    citations: list[Citation]
    disclaimer: str
    answer: str


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
