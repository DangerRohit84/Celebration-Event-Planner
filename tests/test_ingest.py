"""Document ingestion tests (PDF parsing + section-aware chunking)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.ingest import (
    DocumentCapacityError,
    DocumentError,
    DocumentStore,
    chunk_text,
    get_document_store,
    parse_pdf,
    relevant_chunks,
    reset_document_store,
)
from backend.app.main import app
from tests.pdf_support import build_pdf, build_scanned_pdf, build_text_pdf


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_parse_pdf_extracts_pages_and_chunks() -> None:
    """A real PDF must yield its page count and retrievable chunks."""
    document = parse_pdf(build_text_pdf(), "plan.pdf")
    assert document.pages == 2
    assert document.text_length > 0
    assert len(document.chunks) > 0
    assert all(chunk.text.strip() for chunk in document.chunks)
    assert all(chunk.doc_id == document.document_id for chunk in document.chunks)


def test_parse_pdf_rejects_a_non_pdf() -> None:
    """Bytes that are not a PDF must raise a document error."""
    with pytest.raises(DocumentError):
        parse_pdf(b"%PDF-1.4 but truncated garbage", "broken.pdf")


def test_parse_pdf_rejects_a_scanned_document() -> None:
    """A PDF with no extractable text must be rejected."""
    with pytest.raises(DocumentError):
        parse_pdf(build_scanned_pdf(), "scanned.pdf")


def test_chunk_text_is_section_aware() -> None:
    """Chunks must not split a section across arbitrary character counts."""
    text = (
        "Venue Contract\n"
        "Sign the venue contract six weeks ahead.\n"
        "Confirm the final guest count with the caterer.\n"
        "\n"
        "Transport Rules\n"
        "Arrange shuttle transport for guests arriving late.\n"
    )
    chunks = chunk_text(text, max_chars=80)
    assert len(chunks) >= 2
    assert any("Sign the venue contract" in c for c in chunks)
    assert any("shuttle transport" in c for c in chunks)
    # No chunk may end mid-word: every chunk ends on a sentence boundary.
    assert all(c.endswith((".", "!", "?")) for c in chunks)


def test_chunk_text_of_empty_input() -> None:
    """Empty text produces no chunks rather than an error."""
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_relevant_chunks_rank_by_overlap() -> None:
    """Chunks that share terms with the query must rank first."""
    document = parse_pdf(build_text_pdf(), "plan.pdf")
    ranked = relevant_chunks(document, "venue contract guest count", limit=2)
    assert ranked
    assert any("venue contract" in text.lower() for text in ranked)


def test_relevant_chunks_of_unrelated_query() -> None:
    """A query with no overlap yields no excerpts."""
    document = parse_pdf(build_text_pdf(), "plan.pdf")
    assert relevant_chunks(document, "zzzz qqqq", limit=3) == []


def test_document_store_keeps_the_latest_upload() -> None:
    """The most recent upload acts as the session document."""
    store = DocumentStore(max_documents=2)
    first = parse_pdf(build_text_pdf(), "a.pdf")
    second = parse_pdf(build_text_pdf(), "b.pdf")
    store.add(first)
    store.add(second)
    assert store.latest() is second
    assert store.get(first.document_id) is first


def test_document_store_refuses_a_document_when_it_is_full() -> None:
    """The store must refuse a new document instead of dropping an old one."""
    store = DocumentStore(max_documents=1)
    first = parse_pdf(build_text_pdf(), "a.pdf")
    second = parse_pdf(build_text_pdf(), "b.pdf")
    store.add(first)
    with pytest.raises(DocumentCapacityError):
        store.add(second)
    assert store.get(first.document_id) is first
    assert store.count == 1


def test_document_store_capacity_is_configurable() -> None:
    """The configured maximum must be the capacity of the store."""
    store = DocumentStore(max_documents=3)
    assert store.max_documents == 3
    assert store.count == 0


def test_max_documents_setting_caps_the_upload_path(
    monkeypatch: pytest.MonkeyPatch, client: TestClient,
) -> None:
    """``MAX_DOCUMENTS`` must really bound the session document store."""
    monkeypatch.setattr(settings, "max_documents", 2)
    reset_document_store()
    store = get_document_store()
    assert store.max_documents == 2

    for _ in range(2):
        accepted = client.post(
            "/upload",
            files={"file": ("plan.pdf", build_text_pdf(), "application/pdf")},
        )
        assert accepted.status_code == 200

    refused = client.post(
        "/upload",
        files={"file": ("plan.pdf", build_text_pdf(), "application/pdf")},
    )
    assert refused.status_code == 429
    assert refused.headers.get("Retry-After")
    assert store.count == 2


def test_upload_returns_pages_and_chunks(client: TestClient) -> None:
    """The upload response must report the parsed page and chunk counts."""
    r = client.post(
        "/upload",
        files={"file": ("plan.pdf", build_text_pdf(), "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["pages"] == 2
    assert body["chunks"] > 0
    assert body["status"] == "accepted"
    assert body["filename"] == "plan.pdf"
    assert body["size"] > 0


def test_upload_rejects_a_non_pdf(client: TestClient) -> None:
    """A file that is not a PDF must be rejected with a 400."""
    r = client.post(
        "/upload",
        files={"file": ("notes.pdf", b"just some text", "application/pdf")},
    )
    assert r.status_code == 400
    assert "pdf" in r.json()["detail"].lower()


def test_upload_rejects_a_truncated_pdf(client: TestClient) -> None:
    """Magic bytes alone are not enough: the file must really parse."""
    r = client.post(
        "/upload",
        files={"file": ("stub.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert r.status_code == 400


def test_upload_rejects_a_corrupted_pdf_with_a_clean_400(client: TestClient) -> None:
    """A structurally corrupted PDF must fail fast with a 400, never a 500.

    The file keeps a valid header and real objects but its xref/trailer
    region is cut off, so the parser hits a broken structure instead of a
    merely short file.
    """
    corrupted = build_text_pdf()[:-40]
    r = client.post(
        "/upload",
        files={"file": ("broken.pdf", corrupted, "application/pdf")},
    )
    assert r.status_code == 400
    assert "pdf" in r.json()["detail"].lower()


def test_upload_rejects_a_scanned_pdf(client: TestClient) -> None:
    """A scanned document with no text must be rejected with a 400."""
    r = client.post(
        "/upload",
        files={"file": ("scan.pdf", build_scanned_pdf(), "application/pdf")},
    )
    assert r.status_code == 400
    assert "text" in r.json()["detail"].lower()


def test_uploaded_document_feeds_the_ideas_prompt(client: TestClient) -> None:
    """A question asked after an upload must see the document context."""
    r = client.post(
        "/upload",
        files={"file": ("plan.pdf", build_text_pdf(), "application/pdf")},
    )
    assert r.status_code == 200
    assert get_document_store().latest() is not None

    ev = client.post(
        "/events",
        json={
            "name": "W",
            "event_type": "wedding",
            "event_date": "2026-12-01",
            "budget_total": 1000.0,
        },
    )
    eid = ev.json()["event_id"]
    ideas = client.post(
        "/ideas",
        json={"event_id": eid, "query": "venue contract guest count"},
    )
    assert ideas.status_code == 200
    assert ideas.json()["citations"]


def test_multi_page_pdf_is_parsed_per_page() -> None:
    """Chunks must record the page they came from."""
    document = parse_pdf(
        build_pdf([["Page One Text"], ["Page Two Text"]]),
        "two.pdf",
    )
    pages = {chunk.page for chunk in document.chunks}
    assert pages == {1, 2}
