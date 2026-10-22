"""API tests."""

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.main import app
from tests.pdf_support import build_text_pdf


@pytest.fixture()
def client():
    main_module._rate_buckets.clear()
    with TestClient(app) as c:
        yield c
    main_module._rate_buckets.clear()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200


def test_create_event(client):
    r = client.post(
        "/events",
        json={
            "name": "My Wedding",
            "event_type": "wedding",
            "event_date": "2026-12-01",
            "guest_count": 100,
            "budget_total": 50000.0,
        },
    )
    assert r.status_code == 200
    assert "event_id" in r.json()


def test_create_event_validation(client):
    r = client.post("/events", json={"name": "", "event_date": "2026-12-01"})
    assert r.status_code == 422


def test_get_event(client):
    r = client.post(
        "/events",
        json={
            "name": "E",
            "event_type": "birthday",
            "event_date": "2026-12-01",
            "guest_count": 5,
            "budget_total": 100.0,
        },
    )
    eid = r.json()["event_id"]
    g = client.get(f"/events/{eid}")
    assert g.status_code == 200
    assert g.json()["event"]["name"] == "E"
    assert "budget" in g.json()
    assert "timeline" in g.json()
    assert "vendors" in g.json()


def test_get_event_404(client):
    assert client.get("/events/nope").status_code == 404


def test_list_events(client):
    client.post("/events", json={"name": "E1", "event_date": "2026-12-01"})
    r = client.get("/events")
    assert r.status_code == 200
    assert "events" in r.json()


def test_update_event(client):
    r = client.post("/events", json={"name": "E", "event_date": "2026-12-01"})
    eid = r.json()["event_id"]
    u = client.put(f"/events/{eid}", json={"name": "Updated"})
    assert u.status_code == 200
    g = client.get(f"/events/{eid}")
    assert g.json()["event"]["name"] == "Updated"


def test_delete_event(client):
    r = client.post("/events", json={"name": "E", "event_date": "2026-12-01"})
    eid = r.json()["event_id"]
    d = client.delete(f"/events/{eid}")
    assert d.status_code == 200
    assert client.get(f"/events/{eid}").status_code == 404


def test_ideas(client):
    r = client.post(
        "/events",
        json={
            "name": "W",
            "event_type": "wedding",
            "event_date": "2026-12-01",
            "budget_total": 1000.0,
        },
    )
    eid = r.json()["event_id"]
    i = client.post(
        "/ideas", json={"event_id": eid, "query": "outdoor ceremony ideas", "top_k": 3}
    )
    assert i.status_code == 200
    body = i.json()
    assert "disclaimer" in body
    assert "confidence" in body


def test_ask(client):
    r = client.post(
        "/events",
        json={
            "name": "W",
            "event_type": "wedding",
            "event_date": "2026-12-01",
            "budget_total": 1000.0,
        },
    )
    eid = r.json()["event_id"]
    i = client.post("/ask", json={"event_id": eid, "query": "outdoor ceremony ideas"})
    assert i.status_code == 200


def test_export(client):
    r = client.post(
        "/events",
        json={
            "name": "W",
            "event_type": "wedding",
            "event_date": "2026-12-01",
            "budget_total": 1000.0,
        },
    )
    eid = r.json()["event_id"]
    e = client.post("/export", json={"event_id": eid})
    assert e.status_code == 200
    assert "budget" in e.json()
    assert "disclaimer" in e.json()


def test_upload(client):
    r = client.post(
        "/upload",
        files={"file": ("x.pdf", build_text_pdf(), "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "x.pdf"
    assert body["status"] == "accepted"
    assert body["pages"] > 0
    assert body["chunks"] > 0
    assert body["upload_id"]


def test_upload_rejects_bad(client):
    r = client.post("/upload", files={"file": ("x.pdf", b"notpdf", "application/pdf")})
    assert r.status_code == 400
