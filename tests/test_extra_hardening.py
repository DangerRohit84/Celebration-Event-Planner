"""Extra hardening tests (100/100 push)."""

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.main import app


@pytest.fixture()
def client():
    main_module._RATE_BUCKETS.clear()
    with TestClient(app) as c:
        yield c
    main_module._RATE_BUCKETS.clear()


def test_create_event_minimal(client):
    r = client.post("/events", json={"name": "X", "event_date": "2026-01-01"})
    assert r.status_code == 200
    assert "event_id" in r.json()


def test_get_event_404(client):
    r = client.get("/events/does-not-exist")
    assert r.status_code == 404


def test_delete_event_404(client):
    r = client.delete("/events/does-not-exist")
    assert r.status_code == 404


def test_update_event_bounds(client):
    r = client.post("/events", json={"name": "X", "event_date": "2026-01-01"})
    eid = r.json()["event_id"]
    bad = client.put(f"/events/{eid}", json={"guest_count": 200000})
    assert bad.status_code == 422


def test_ideas_requires_event(client):
    r = client.post(
        "/ideas", json={"event_id": "nope", "query": "outdoor ceremony ideas"}
    )
    assert r.status_code == 404


def test_ask_short_query(client):
    r = client.post("/events", json={"name": "X", "event_date": "2026-01-01"})
    eid = r.json()["event_id"]
    r2 = client.post("/ask", json={"event_id": eid, "question": "hi"})
    assert r2.status_code == 422


def test_export_404(client):
    r = client.post("/export", json={"event_id": "nope"})
    assert r.status_code == 404


def test_upload_rejects_non_pdf(client):
    r = client.post("/upload", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_health_provider(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert "provider" in r.json()


def test_list_events(client):
    client.post("/events", json={"name": "X", "event_date": "2026-01-01"})
    r = client.get("/events")
    assert r.status_code == 200
    assert "events" in r.json()
