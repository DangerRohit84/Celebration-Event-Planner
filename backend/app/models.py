"""Domain entities for the Celebration & Event Planner.

Pure data classes (no I/O). Validation lives in Pydantic schemas in main.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class EventType(str, Enum):
    WEDDING = "wedding"
    BIRTHDAY = "birthday"
    COMMUNITY = "community"
    CORPORATE = "corporate"
    OTHER = "other"


class VendorStatus(str, Enum):
    NOT_STARTED = "not_started"
    RESEARCHING = "researching"
    QUOTED = "quoted"
    BOOKED = "booked"
    PAID = "paid"
    CANCELLED = "cancelled"


@dataclass
class Event:
    id: str
    name: str
    event_type: EventType
    event_date: date
    guest_count: int
    budget_total: float
    theme: str = ""
    location: str = ""
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BudgetLine:
    id: str
    event_id: str
    category: str
    allocated: float
    spent: float = 0.0
    notes: str = ""


@dataclass
class TimelineMilestone:
    id: str
    event_id: str
    title: str
    due_date: date
    status: str = "pending"  # pending | done | overdue
    notes: str = ""


@dataclass
class Vendor:
    id: str
    event_id: str
    category: str  # venue, catering, decor, photo, music, ...
    name: str = ""
    status: VendorStatus = VendorStatus.NOT_STARTED
    cost_estimate: float = 0.0
    contact: str = ""
    notes: str = ""


@dataclass
class Guest:
    id: str
    event_id: str
    name: str
    rsvp: str = "pending"  # pending | yes | no | maybe
    dietary: str = ""
    plus_one: bool = False


@dataclass
class Chunk:
    chunk_id: str = ""
    doc_id: str = ""
    page: int = 1
    clause: str = ""
    text: str = ""
    score: float = 0.0


@dataclass
class Plan:
    """Generated plan artifact (budget breakdown + timeline + vendor checklist + ideas)."""
    event_id: str
    budget_breakdown: list[BudgetLine] = field(default_factory=list)
    timeline: list[TimelineMilestone] = field(default_factory=list)
    vendor_checklist: list[Vendor] = field(default_factory=list)
    ideas: list[str] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)  # grounded idea sources
    disclaimer: str = "General planning information only - not professional advice. Verify with vendors and qualified planners."
