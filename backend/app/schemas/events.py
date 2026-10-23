"""Pydantic event schemas: the event wire format.

These define the exact JSON the server returns for events, their budget
lines, milestones, vendors, and the export projections.
"""

from __future__ import annotations

from pydantic import BaseModel


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
