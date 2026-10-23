"""Pydantic request schemas: what the client may send.

Every free-text field is length-bounded so a single request cannot ship an
unbounded string into retrieval, the prompt builder, or the store.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    """Schema for creating an event."""

    name: str = Field(..., min_length=1, max_length=200)
    event_type: str = Field("other", max_length=50)
    event_date: str = Field(..., max_length=20)
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

    event_id: str = Field(..., max_length=128)
    query: str = Field(..., min_length=3, max_length=500)
    top_k: int = Field(5, ge=1, le=10)
    plain_language: bool = False


class AskRequest(BaseModel):
    """Schema for an ask request.

    The free-text fields are bounded (2000 matches the ``notes`` cap) so a
    single request cannot ship an unbounded string into retrieval and the
    prompt builder; ``event_id`` matches the ``ExportRequest`` cap.
    """

    event_id: str | None = Field(None, max_length=128)
    query: str | None = Field(None, min_length=3, max_length=2000)
    question: str | None = Field(None, min_length=3, max_length=2000)
    top_k: int = Field(5, ge=1, le=10)
    plain_language: bool = False


class ExportRequest(BaseModel):
    """Schema for an export request."""

    event_id: str = Field(..., min_length=1, max_length=128)
