"""Pytest fixtures."""

import pytest

from backend.app.storage import InMemoryStore, reset_store


@pytest.fixture(autouse=True)
def _reset_store():
    reset_store(InMemoryStore(max_events=100))
    yield
    reset_store(None)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from backend.app.main import app

    return TestClient(app)
