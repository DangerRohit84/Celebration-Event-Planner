"""Planner tests."""
from backend.app.planner import budget_breakdown, timeline_for, vendor_checklist, total_allocated
from backend.app.models import Event, EventType
from datetime import date


def test_budget_sums_to_total():
    ev = Event(id="e1", name="W", event_type=EventType.WEDDING, event_date=date(2026, 6, 1), guest_count=100, budget_total=10000.0)
    lines = budget_breakdown(ev)
    assert len(lines) > 0
    assert abs(total_allocated(lines) - 10000.0) < 1.0


def test_timeline_nonempty():
    ev = Event(id="e1", name="W", event_type=EventType.WEDDING, event_date=date(2026, 6, 1), guest_count=100, budget_total=10000.0)
    ms = timeline_for(ev)
    assert len(ms) > 0


def test_vendor_checklist():
    ev = Event(id="e1", name="W", event_type=EventType.WEDDING, event_date=date(2026, 6, 1), guest_count=100, budget_total=10000.0)
    vs = vendor_checklist(ev)
    assert len(vs) > 0


def test_all_event_types():
    for et in ["wedding", "birthday", "community", "corporate", "other"]:
        ev = Event(id="e", name="E", event_type=EventType(et), event_date=date(2026, 6, 1), guest_count=10, budget_total=1000.0)
        assert budget_breakdown(ev)
        assert timeline_for(ev)
        assert vendor_checklist(ev)
