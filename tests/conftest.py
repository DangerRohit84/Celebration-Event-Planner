"""Pytest fixtures."""

import pytest

from backend.app.ingest import reset_document_store
from backend.app.storage import InMemoryStore, reset_store


@pytest.fixture(autouse=True)
def _reset_store():
    reset_store(InMemoryStore(max_events=100))
    yield
    reset_store(None)


@pytest.fixture(autouse=True)
def _reset_documents():
    """Keep uploaded documents from leaking between tests."""
    reset_document_store()
    yield
    reset_document_store()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from backend.app.main import app

    return TestClient(app)
