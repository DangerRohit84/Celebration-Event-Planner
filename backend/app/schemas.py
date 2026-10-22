"""Pydantic request/response schemas for the API."""

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
