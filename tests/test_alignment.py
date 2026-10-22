"""Alignment tests."""

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.main import app
from backend.app.prompting import CANNOT_DETERMINE, DISCLAIMER


def test_disclaimer_present():
    assert "not professional advice" in DISCLAIMER or "General planning" in DISCLAIMER


def test_cannot_determine_constant():
    assert "Cannot Determine" in CANNOT_DETERMINE


@pytest.fixture()
def client():
    main_module._RATE_BUCKETS.clear()
    with TestClient(app) as c:
        yield c
    main_module._RATE_BUCKETS.clear()


def test_disclaimer_on_ideas(client):
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
    assert (
        "not professional advice" in i.json()["disclaimer"].lower()
        or "General" in i.json()["disclaimer"]
    )


def test_export_disclaimer(client):
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
    assert "disclaimer" in e.json()
