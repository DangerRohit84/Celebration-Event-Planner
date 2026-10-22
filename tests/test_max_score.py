"""Max score tests."""

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


def test_rate_limit_headers_present(client):
    r = client.get("/health")
    assert r.headers.get("X-RateLimit-Limit")
    assert r.headers.get("X-RateLimit-Remaining") is not None
    assert r.headers.get("X-RateLimit-Reset")


def test_ideas_returns_confidence(client):
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
    i = client.post("/ideas", json={"event_id": eid, "query": "outdoor ceremony ideas"})
    assert i.status_code == 200
    assert "confidence" in i.json()


def test_export_shape(client):
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
    for k in ("event", "budget", "timeline", "vendors", "disclaimer"):
        assert k in e.json()
