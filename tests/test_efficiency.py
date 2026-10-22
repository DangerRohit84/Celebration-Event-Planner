"""Efficiency tests."""

import time

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.main import app


@pytest.fixture()
def client():
    main_module._rate_buckets.clear()
    with TestClient(app) as c:
        yield c
    main_module._rate_buckets.clear()


def test_health_fast(client):
    t = time.perf_counter()
    r = client.get("/health")
    assert r.status_code == 200
    assert (time.perf_counter() - t) < 1.0


def test_search_sub_second():
    from backend.app.retrieval import search

    t0 = time.time()
    search("outdoor ceremony", top_k=5)
    dt = time.time() - t0
    assert dt < 1.0


def test_top_k_clamped():
    from backend.app.retrieval import search

    hits = search("outdoor ceremony", top_k=100)
    assert len(hits) <= 10


def test_bounded_oversize(client):
    big = b"%PDF-1.4 fake" + b"x" * (11 * 1024 * 1024)
    r = client.post("/upload", files={"file": ("big.pdf", big, "application/pdf")})
    assert r.status_code == 413 or r.status_code == 400


def test_process_time_header(client):
    r = client.get("/health")
    assert r.headers.get("X-Process-Time")
