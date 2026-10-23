"""Boundary and failure-mode tests.

These pin the exact edges of the public API contract: numeric limits, the
storage-exhaustion path, the hard-refusal path, provider outages, CORS
allowlist parsing, rate-limit spoof resistance, and header coverage.
"""

import time
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.config import parse_allowed_origins, settings
from backend.app.main import app
from backend.app.prompting import CANNOT_DETERMINE
from backend.app.security import validate_pre_parse
from backend.app.storage import InMemoryStore, reset_store


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """Return a test client with a clean rate-limit bucket store.

    Yields:
        A test client bound to the application.
    """
    main_module._rate_buckets.clear()
    with TestClient(app) as c:
        yield c
    main_module._rate_buckets.clear()


def _event(**overrides: object) -> dict:
    """Build an event payload with optional field overrides.

    Args:
        **overrides: Fields to replace in the default payload.

    Returns:
        A JSON-ready event creation payload.
    """
    payload: dict[str, object] = {
        "name": "Boundary",
        "event_type": "wedding",
        "event_date": "2026-12-01",
    }
    payload.update(overrides)
    return payload


def _create(client: TestClient, **overrides: object) -> str:
    """Create an event and return its identifier.

    Args:
        client: Test client used to issue the request.
        **overrides: Fields to replace in the default payload.

    Returns:
        The identifier of the newly created event.
    """
    r = client.post("/events", json=_event(**overrides))
    assert r.status_code == 200, r.text
    return r.json()["event_id"]


# --- numeric boundaries ---------------------------------------------------


def test_guest_count_zero_is_accepted(client: TestClient) -> None:
    """Zero guests is a valid (if unusual) event and must be accepted."""
    r = client.post("/events", json=_event(guest_count=0))
    assert r.status_code in (200, 201)
    assert "event_id" in r.json()


def test_budget_total_zero_is_accepted(client: TestClient) -> None:
    """A zero budget is a valid boundary and must be accepted."""
    r = client.post("/events", json=_event(budget_total=0.0))
    assert r.status_code in (200, 201)
    assert "event_id" in r.json()


def test_guest_count_max_is_accepted(client: TestClient) -> None:
    """The documented maximum guest count is inclusive."""
    r = client.post("/events", json=_event(guest_count=100000))
    assert r.status_code in (200, 201)


def test_guest_count_above_max_is_rejected(client: TestClient) -> None:
    """One guest beyond the documented maximum must be rejected."""
    r = client.post("/events", json=_event(guest_count=100001))
    assert r.status_code == 422


def test_budget_total_negative_is_rejected(client: TestClient) -> None:
    """A negative budget must be rejected."""
    r = client.post("/events", json=_event(budget_total=-1))
    assert r.status_code == 422


@pytest.mark.parametrize("top_k", [0, 11])
def test_top_k_out_of_range_is_rejected(client: TestClient, top_k: int) -> None:
    """top_k outside 1..10 must be rejected by validation."""
    eid = _create(client)
    r = client.post(
        "/ideas", json={"event_id": eid, "query": "outdoor ceremony", "top_k": top_k},
    )
    assert r.status_code == 422


@pytest.mark.parametrize("top_k", [1, 10])
def test_top_k_bounds_are_accepted(client: TestClient, top_k: int) -> None:
    """The inclusive top_k bounds must be accepted."""
    eid = _create(client)
    r = client.post(
        "/ideas", json={"event_id": eid, "query": "outdoor ceremony", "top_k": top_k},
    )
    assert r.status_code == 200
    assert "citations" in r.json()


# --- failure modes --------------------------------------------------------


def test_storage_exhaustion_returns_429_with_retry_after(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A saturated event store must answer 429 and tell the client to retry."""
    monkeypatch.setattr(settings, "max_store_events", 2)
    reset_store(InMemoryStore(max_events=settings.max_store_events))
    assert client.post("/events", json=_event()).status_code == 200
    assert client.post("/events", json=_event()).status_code == 200
    r = client.post("/events", json=_event())
    assert r.status_code == 429
    assert r.headers.get("Retry-After")


@pytest.mark.parametrize(
    "query",
    [
        "quantum mechanical supercomputing",
        "the and of to a in is it",
        "what is the capital of France",
        "best honeymoon destination in Maldives",
    ],
)
def test_hard_refusal_when_nothing_can_be_grounded(
    client: TestClient, query: str,
) -> None:
    """Unanswerable questions must refuse instead of inventing ideas."""
    eid = _create(client)
    r = client.post("/ideas", json={"event_id": eid, "query": query})
    assert r.status_code == 200
    body = r.json()
    assert body["confidence"] == "Cannot Determine"
    assert body["citations"] == []
    assert body["disclaimer"]
    assert body["answer"] == CANNOT_DETERMINE
    assert body["ideas"] == []


def test_provider_failure_degrades_gracefully(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing provider must never turn into a 500 or leak a traceback."""

    def boom(_self: object, _prompt: str, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("upstream provider exploded")

    monkeypatch.setattr("backend.app.llm.base.EchoProvider.answer", boom)
    eid = _create(client)
    r = client.post("/ideas", json={"event_id": eid, "query": "outdoor ceremony"})
    assert r.status_code in (200, 503)
    assert "Traceback" not in r.text
    assert "RuntimeError" not in r.text
    if r.status_code == 200:
        assert r.json()["answer"]


def test_provider_factory_failure_degrades_gracefully(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A provider that cannot even be constructed must still be handled."""

    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("no provider available")

    monkeypatch.setattr("backend.app.routes.answering.build_provider", boom)
    eid = _create(client)
    r = client.post("/ideas", json={"event_id": eid, "query": "outdoor ceremony"})
    assert r.status_code in (200, 503)
    assert "Traceback" not in r.text
    assert "RuntimeError" not in r.text
    if r.status_code == 200:
        assert r.json()["answer"]


def test_pre_parse_rejects_unsupported_call_shapes() -> None:
    """Only the two documented call shapes are accepted."""
    with pytest.raises(TypeError):
        # The type system forbids this shape on purpose; the runtime guard
        # is what is under test here.
        validate_pre_parse("x.pdf", "application/pdf", 8)  # type: ignore[call-overload]
    with pytest.raises(TypeError):
        validate_pre_parse(  # type: ignore[call-overload]
            b"%PDF-1.4", "x.pdf", "application/pdf", b"%PDF-1.4"
        )


def test_pre_parse_accepts_both_documented_call_shapes() -> None:
    """The canonical and legacy call shapes both validate a good upload."""
    assert validate_pre_parse("x.pdf", "application/pdf", 8, b"%PDF-1.4") is True
    assert validate_pre_parse(b"%PDF-1.4", "x.pdf", "application/pdf") is True


# --- CORS allowlist -------------------------------------------------------


def test_parse_allowed_origins_rejects_wildcard() -> None:
    """A wildcard must never survive the parser."""
    assert parse_allowed_origins("*") == []


def test_parse_allowed_origins_splits_and_trims() -> None:
    """Valid origins are split on commas and trimmed."""
    assert parse_allowed_origins("https://a.com, https://b.com") == [
        "https://a.com",
        "https://b.com",
    ]


def test_parse_allowed_origins_drops_malformed_entries() -> None:
    """Malformed origins are dropped rather than forwarded."""
    assert parse_allowed_origins("not-an-origin, ftp://x.com, https://ok.com") == [
        "https://ok.com",
    ]


def test_parse_allowed_origins_drops_wildcard_among_valid_entries() -> None:
    """One wildcard poisons the whole list, so it is dropped as well."""
    assert parse_allowed_origins("*, https://ok.com") == ["https://ok.com"]


def test_parse_allowed_origins_keeps_ports() -> None:
    """An explicit port is a valid origin."""
    assert parse_allowed_origins("http://localhost:8000") == ["http://localhost:8000"]


def test_settings_allowed_origins_never_contains_wildcard() -> None:
    """The live configuration can never contain a wildcard."""
    for origin in settings.allowed_origins:
        assert "*" not in origin


def test_non_allowlisted_origin_gets_no_cors_header(client: TestClient) -> None:
    """A cross-origin caller outside the allowlist gets no CORS permission."""
    r = client.get("/health", headers={"Origin": "https://evil.test"})
    assert r.headers.get("Access-Control-Allow-Origin") != "*"
    assert r.headers.get("Access-Control-Allow-Origin") is None


def test_empty_allowlist_blocks_cross_origin() -> None:
    """An empty allowlist must block cross-origin calls, not enable them."""
    mini = FastAPI()
    mini.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @mini.get("/ping")
    def ping() -> dict:
        """Return a trivial payload.

        Returns:
            A mapping acknowledging the request.
        """
        return {"ok": True}
    with TestClient(mini) as c:
        simple = c.get("/ping", headers={"Origin": "https://evil.test"})
        assert simple.headers.get("Access-Control-Allow-Origin") is None
        preflight = c.options(
            "/ping",
            headers={
                "Origin": "https://evil.test",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert preflight.status_code >= 400
        assert preflight.headers.get("Access-Control-Allow-Origin") is None


# --- rate limiting --------------------------------------------------------


def test_rate_limit_ignores_forwarded_for_header(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A spoofed X-Forwarded-For must not create a second bucket."""
    monkeypatch.setattr(settings, "rate_limit_per_min", 1)
    main_module._rate_buckets.clear()
    first = client.get("/health", headers={"X-Forwarded-For": "1.1.1.1"})
    assert first.status_code == 200
    second = client.get("/health", headers={"X-Forwarded-For": "2.2.2.2"})
    assert second.status_code == 429
    assert second.headers.get("Retry-After")


def test_rate_bucket_store_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bucket store must never grow past its configured cap."""
    monkeypatch.setattr(settings, "max_rate_buckets", 3)
    main_module._rate_buckets.clear()
    try:
        now = time.time()
        for i in range(10):
            main_module._rate_buckets[f"ip-{i}"] = [now]
        main_module._evict_rate_buckets()
        assert len(main_module._rate_buckets) <= 3
    finally:
        main_module._rate_buckets.clear()


def test_rate_bucket_window_is_sliding(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timestamps older than the window are dropped from the bucket."""
    monkeypatch.setattr(settings, "rate_limit_per_min", 5)
    main_module._rate_buckets.clear()
    bucket = main_module._rate_buckets["testclient"] = []
    bucket.extend([time.time() - 3600, time.time() - 120])
    client.get("/health")
    remaining = main_module._rate_buckets["testclient"]
    assert len(remaining) == 1
    assert remaining[0] > time.time() - 60


# --- header coverage ------------------------------------------------------


def test_security_headers_present_on_404(client: TestClient) -> None:
    """A 404 must still carry the full security header set."""
    r = client.get("/definitely-not-a-route")
    assert r.status_code == 404
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
    assert r.headers.get("Cache-Control") == "no-store"
    assert r.headers.get("X-Process-Time")
    assert r.headers.get("X-RateLimit-Limit")
    assert r.headers.get("X-RateLimit-Remaining")
    assert r.headers.get("X-RateLimit-Reset")


def test_security_headers_present_on_422(client: TestClient) -> None:
    """A validation error must still carry the security header set."""
    r = client.post("/events", json={"name": "", "event_date": "2026-12-01"})
    assert r.status_code == 422
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Cache-Control") == "no-store"


def test_security_headers_present_on_static_files(client: TestClient) -> None:
    """Static assets must also carry the security header set."""
    r = client.get("/static/styles.css")
    assert r.status_code == 200
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
