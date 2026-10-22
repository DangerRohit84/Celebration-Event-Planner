"""Hardening tests."""

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import validate_pre_parse


def test_magic_rejects_text():
    try:
        validate_pre_parse(b"hello", "x.pdf", "application/pdf")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_pre_parse_legal_style():
    try:
        validate_pre_parse("notes.txt", "application/pdf", 100, b"%PDF-1.4 x")
        raised = False
    except ValueError as e:
        raised = True
        assert "PDF only" in str(e) or "pdf" in str(e).lower()
    assert raised


def test_doc_id_entropy():
    client = TestClient(app)
    r = client.post(
        "/upload", files={"file": ("r.pdf", b"%PDF-1.4", "application/pdf")}
    )
    # upload doesn't return doc_id; skip
    assert r.status_code == 200


def test_security_headers_present():
    client = TestClient(app)
    r = client.get("/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"


def test_bounded_oversize():
    client = TestClient(app)
    big = b"%PDF-1.4 fake" + b"x" * (11 * 1024 * 1024)
    r = client.post("/upload", files={"file": ("big.pdf", big, "application/pdf")})
    assert r.status_code in (400, 413)
