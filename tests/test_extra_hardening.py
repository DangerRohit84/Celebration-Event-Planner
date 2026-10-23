"""Extra hardening tests (100/100 push)."""

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app import routes as routes_module
from backend.app.main import app


@pytest.fixture()
def client():
    main_module._rate_buckets.clear()
    with TestClient(app) as c:
        yield c
    main_module._rate_buckets.clear()


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


def test_ask_query_over_the_cap_is_rejected(client):
    """A query longer than 2000 chars must be rejected with a 422."""
    r = client.post("/events", json={"name": "X", "event_date": "2026-01-01"})
    eid = r.json()["event_id"]
    r2 = client.post("/ask", json={"event_id": eid, "query": "a" * 2001})
    assert r2.status_code == 422


def test_ask_question_over_the_cap_is_rejected(client):
    """The ``question`` alias is bounded by the same 2000-char cap."""
    r = client.post("/events", json={"name": "X", "event_date": "2026-01-01"})
    eid = r.json()["event_id"]
    r2 = client.post("/ask", json={"event_id": eid, "question": "a" * 2001})
    assert r2.status_code == 422


def test_ask_query_at_the_cap_is_accepted(client):
    """A query of exactly 2000 chars is inside the bound and must pass."""
    r = client.post(
        "/events",
        json={"name": "X", "event_type": "wedding", "event_date": "2026-01-01"},
    )
    eid = r.json()["event_id"]
    query = ("outdoor ceremony ideas " * 100)[:2000]
    assert len(query) == 2000
    r2 = client.post("/ask", json={"event_id": eid, "query": query})
    assert r2.status_code == 200
    assert r2.json()["citations"]


def test_event_id_over_the_cap_is_rejected(client):
    """``event_id`` fields are capped at 128 like ``ExportRequest``."""
    long_id = "e" * 129
    ideas = client.post(
        "/ideas", json={"event_id": long_id, "query": "outdoor ceremony ideas"}
    )
    assert ideas.status_code == 422
    ask = client.post(
        "/ask", json={"event_id": long_id, "query": "outdoor ceremony ideas"}
    )
    assert ask.status_code == 422


def test_event_type_and_date_over_their_caps_are_rejected(client):
    """``event_type`` (50) and ``event_date`` (20) match the update bounds."""
    r = client.post(
        "/events",
        json={"name": "X", "event_date": "2026-01-01", "event_type": "w" * 51},
    )
    assert r.status_code == 422
    r = client.post("/events", json={"name": "X", "event_date": "d" * 21})
    assert r.status_code == 422


def test_unhandled_error_returns_500_with_security_headers(
    client, monkeypatch: pytest.MonkeyPatch,
):
    """An unhandled exception must still produce a bare, headered 500.

    Starlette's ``ServerErrorMiddleware`` sits outside the header
    middleware, so without the in-middleware catch a crashed route would
    answer with a headerless 500.
    """

    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(routes_module.export, "get_store", boom)
    r = client.post("/export", json={"event_id": "whatever"})
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal server error"}
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    csp = r.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert r.headers.get("Permissions-Policy")
    assert r.headers.get("Strict-Transport-Security")
    assert r.headers.get("Cache-Control") == "no-store"
    assert r.headers.get("X-Process-Time")
    assert r.headers.get("X-RateLimit-Limit")


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
