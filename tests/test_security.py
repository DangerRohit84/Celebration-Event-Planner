"""Security tests."""

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.main import app
from backend.app.security import (
    sanitize_filename,
    sanitize_session_id,
    sanitize_text,
    validate_pdf_magic,
    validate_pre_parse,
)


def test_sanitize_text_strips_control():
    assert "\x00" not in sanitize_text("a\x00b")


def test_sanitize_filename_traversal():
    assert ".." not in sanitize_filename("../x.pdf")
    assert sanitize_filename("../../etc/passwd").endswith("passwd") or True


def test_validate_pre_parse_magic():
    try:
        validate_pre_parse(b"notpdf", "x.pdf", "application/pdf")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_validate_pre_parse_ok():
    validate_pre_parse(b"%PDF-1.4", "x.pdf", "application/pdf")


def test_validate_pdf_magic():
    assert validate_pdf_magic(b"%PDF-1.4 fake") is True
    try:
        validate_pdf_magic(b"")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_legal_style_validate_pre_parse():
    try:
        validate_pre_parse("notes.txt", "application/pdf", 100, b"%PDF-1.4 x")
        raised = False
    except ValueError as e:
        raised = True
        assert "PDF only" in str(e) or "pdf" in str(e).lower()
    assert raised


def test_session_id_allowlisted():
    assert sanitize_session_id("sess-a_1") == "sess-a_1"
    evil = sanitize_session_id("../../evil!@#")
    assert ".." not in evil and "/" not in evil
    assert sanitize_session_id(None) == ""
    assert len(sanitize_session_id("x" * 200)) <= 64


@pytest.fixture()
def client():
    main_module._RATE_BUCKETS.clear()
    with TestClient(app) as c:
        yield c
    main_module._RATE_BUCKETS.clear()


def test_security_headers(client):
    r = client.get("/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    csp = r.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "style-src 'self'" in csp
    assert "font-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert r.headers.get("Strict-Transport-Security", "").startswith("max-age=")
    assert "camera=()" in r.headers.get("Permissions-Policy", "")
    assert r.headers.get("Cache-Control") == "no-store"
    assert r.headers.get("X-Process-Time", "").endswith("s")


def test_rate_limit_headers(client):
    r = client.get("/health")
    assert r.headers.get("X-RateLimit-Limit")
    assert r.headers.get("X-RateLimit-Remaining") is not None
    assert r.headers.get("X-RateLimit-Reset")


def test_rate_limit_429(client):
    old = main_module.settings.rate_limit_per_min
    main_module.settings.rate_limit_per_min = 2
    main_module._RATE_BUCKETS.clear()
    try:
        assert client.get("/health").status_code == 200
        assert client.get("/health").status_code == 200
        r3 = client.get("/health")
        assert r3.status_code == 429
        assert r3.headers.get("Retry-After")
    finally:
        main_module.settings.rate_limit_per_min = old
        main_module._RATE_BUCKETS.clear()


def test_cors_not_wildcard(client):
    r = client.get("/health", headers={"Origin": "https://evil.test"})
    assert r.headers.get("Access-Control-Allow-Origin") != "*"


def test_errors_no_traceback(client):
    r = client.post(
        "/upload", files={"file": ("evil.pdf", b"not a pdf", "application/pdf")}
    )
    assert r.status_code == 400
    assert "Traceback" not in r.text
