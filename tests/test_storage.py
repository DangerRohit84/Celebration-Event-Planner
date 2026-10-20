"""Storage tests."""
from backend.app.storage import get_store, InMemoryStore, CapacityError, new_id, SQLiteStore
from backend.app.models import Event, EventType
from datetime import date
import os
import tempfile


def test_create_and_get():
    store = get_store()
    ev = Event(id=new_id(), name="Test", event_type=EventType.BIRTHDAY,
               event_date=date(2026, 12, 1), guest_count=10, budget_total=1000.0)
    store.create_event(ev)
    got = store.get_event(ev.id)
    assert got is not None
    assert got.name == "Test"


def test_capacity():
    store = InMemoryStore(max_events=1)
    ev = Event(id=new_id(), name="A", event_type=EventType.OTHER, event_date=date(2026, 1, 1), guest_count=1, budget_total=1.0)
    store.create_event(ev)
    ev2 = Event(id=new_id(), name="B", event_type=EventType.OTHER, event_date=date(2026, 1, 1), guest_count=1, budget_total=1.0)
    try:
        store.create_event(ev2)
        raised = False
    except CapacityError:
        raised = True
    assert raised


def test_sqlite_persistent():
    d = tempfile.mkdtemp()
    path = os.path.join(d, "t.db")
    s = SQLiteStore(path)
    ev = Event(id=new_id(), name="P", event_type=EventType.OTHER, event_date=date(2026, 1, 1), guest_count=1, budget_total=1.0)
    s.create_event(ev)
    s2 = SQLiteStore(path)
    assert s2.get_event(ev.id) is not None


def test_list_events():
    store = InMemoryStore(max_events=10)
    for i in range(3):
        store.create_event(Event(id=new_id(), name=f"E{i}", event_type=EventType.OTHER, event_date=date(2026, 1, 1), guest_count=1, budget_total=1.0))
    assert len(store.list_events(limit=2)) == 2
    assert len(store.list_events(limit=10, offset=2)) == 1


def test_delete_event():
    store = InMemoryStore(max_events=10)
    ev = Event(id=new_id(), name="D", event_type=EventType.OTHER, event_date=date(2026, 1, 1), guest_count=1, budget_total=1.0)
    store.create_event(ev)
    assert store.delete_event(ev.id) is True
    assert store.get_event(ev.id) is None
    assert store.delete_event("nope") is False
