"""Plain-language toggle tests.

The toggle is a shipped feature: a checkbox in the UI, a flag on the wire,
a different prompt, and a shorter rendering. These tests pin every link in
that chain so the feature cannot silently regress into a no-op.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.llm.base import EchoProvider
from backend.app.main import app
from backend.app.prompting import (
    PLAIN_HEADER,
    PLAIN_LANGUAGE_RULE,
    STANDARD_HEADER,
    build_ideas_prompt,
    render_grounded_ideas,
)

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
VIDEO_SCRIPT = (ROOT / "docs" / "VIDEO_SCRIPT.md").read_text(encoding="utf-8")

HITS = [
    {"id": "w1", "text": "Outdoor garden ceremony with string lights.", "score": 0.9},
    {"id": "w2", "text": "Buffet with live stations keeps guests engaged.", "score": 0.4},
]

# Representative questions that must all ground in the corpus.
REPRESENTATIVE_QUERIES = [
    "outdoor ceremony ideas",
    "budget-friendly decor ideas for a garden wedding",
    "photo booth props and instant prints",
    "guest favor and entertainment",
    "digital invitations 6 weeks ahead with RSVP tracking",
    "day-of timeline shared with all vendors",
    "buffet with live stations",
    "seasonal flowers and string lights",
    "rsvp tracking and dietary capture",
    "guests engaged and per-plate cost",
]


def _demo_queries() -> list[str]:
    """Return the sample queries the video script tells the presenter to ask.

    Returns:
        The quoted questions listed in ``docs/VIDEO_SCRIPT.md``.
    """
    section = VIDEO_SCRIPT.split("## Sample ask queries", 1)[1]
    return re.findall(r'^- "([^"]+)"$', section, re.MULTILINE)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _event(client: TestClient) -> str:
    """Create a wedding event and return its identifier.

    Args:
        client: The HTTP client to use.

    Returns:
        The identifier of the created event.
    """
    r = client.post(
        "/events",
        json={
            "name": "W",
            "event_type": "wedding",
            "event_date": "2026-12-01",
            "budget_total": 1000.0,
        },
    )
    return r.json()["event_id"]


def test_prompt_changes_with_plain_language() -> None:
    """The plain-language rule must only appear when the flag is set."""
    standard = build_ideas_prompt("outdoor ceremony", HITS, "wedding")
    plain = build_ideas_prompt("outdoor ceremony", HITS, "wedding", True)
    assert PLAIN_LANGUAGE_RULE not in standard
    assert PLAIN_LANGUAGE_RULE in plain
    assert plain != standard


def test_prompt_includes_uploaded_document_context() -> None:
    """Uploaded document excerpts must reach the prompt."""
    with_doc = build_ideas_prompt(
        "venue contract", HITS, "wedding", document_chunks=["Sign six weeks ahead."],
    )
    assert "<document_context>" in with_doc
    assert "Sign six weeks ahead." in with_doc
    assert "<document_context>" not in build_ideas_prompt(
        "venue contract", HITS, "wedding",
    )


def test_echo_provider_renders_plain_language_differently() -> None:
    """The offline provider must produce a visibly different answer."""
    prompt = build_ideas_prompt("outdoor ceremony", HITS, "wedding")
    standard = EchoProvider().answer(prompt)
    plain = EchoProvider().answer(prompt, plain_language=True)
    assert standard != plain
    assert PLAIN_HEADER in plain
    assert STANDARD_HEADER in standard
    assert len(plain) < len(standard)


def test_grounded_renderer_supports_plain_language() -> None:
    """The last-resort renderer must honour the flag too."""
    standard = render_grounded_ideas(HITS)
    plain = render_grounded_ideas(HITS, plain_language=True)
    assert standard != plain
    assert PLAIN_HEADER in plain
    assert "[w1]" not in plain
    assert len(plain) < len(standard)


def test_plain_rendering_is_shorter_for_most_queries(client: TestClient) -> None:
    """The plain rendering must be shorter, not merely differently worded."""
    eid = _event(client)
    shorter = 0
    for query in REPRESENTATIVE_QUERIES:
        standard = client.post(
            "/ideas", json={"event_id": eid, "query": query},
        ).json()["answer"]
        plain = client.post(
            "/ideas",
            json={"event_id": eid, "query": query, "plain_language": True},
        ).json()["answer"]
        assert len(plain) <= len(standard), f"plain rendering grew for {query!r}"
        if len(plain) < len(standard):
            shorter += 1
    assert shorter >= 8, (
        f"only {shorter} of {len(REPRESENTATIVE_QUERIES)} plain renderings "
        "were shorter than the standard ones"
    )


def test_plain_rendering_is_never_longer_for_the_demo_queries(
    client: TestClient,
) -> None:
    """Every query the video script tells the presenter to ask stays shorter."""
    eid = _event(client)
    queries = _demo_queries()
    assert queries, "the video script lists no sample queries"
    for query in queries:
        standard = client.post(
            "/ideas", json={"event_id": eid, "query": query},
        ).json()["answer"]
        plain = client.post(
            "/ideas",
            json={"event_id": eid, "query": query, "plain_language": True},
        ).json()["answer"]
        assert len(plain) <= len(standard), f"plain rendering grew for {query!r}"


def test_api_plain_language_flag_changes_the_answer(client: TestClient) -> None:
    """The same question answered in both modes must differ."""
    eid = _event(client)
    standard = client.post(
        "/ideas",
        json={
            "event_id": eid,
            "query": "outdoor ceremony ideas",
            "plain_language": False,
        },
    )
    plain = client.post(
        "/ideas",
        json={
            "event_id": eid,
            "query": "outdoor ceremony ideas",
            "plain_language": True,
        },
    )
    assert standard.status_code == 200
    assert plain.status_code == 200
    assert standard.json()["plain_language"] is False
    assert plain.json()["plain_language"] is True
    assert standard.json()["answer"] != plain.json()["answer"]
    # The citations are the same source ids in both modes.
    assert [c["id"] for c in standard.json()["citations"]] == [
        c["id"] for c in plain.json()["citations"]
    ]


def test_ask_endpoint_accepts_plain_language(client: TestClient) -> None:
    """POST /ask must accept and honour the flag as well."""
    eid = _event(client)
    plain = client.post(
        "/ask",
        json={
            "event_id": eid,
            "query": "outdoor ceremony ideas",
            "plain_language": True,
        },
    )
    assert plain.status_code == 200
    assert plain.json()["plain_language"] is True


def test_plain_language_defaults_to_false(client: TestClient) -> None:
    """Omitting the flag keeps the standard behaviour."""
    eid = _event(client)
    r = client.post(
        "/ideas", json={"event_id": eid, "query": "outdoor ceremony ideas"},
    )
    assert r.status_code == 200
    assert r.json()["plain_language"] is False


def test_ui_exposes_the_toggle() -> None:
    """The frontend must ship the checkbox and its label."""
    assert 'id="plain"' in HTML
    assert 'type="checkbox"' in HTML
    assert 'for="plain"' in HTML
    assert "Simple language" in HTML
    assert 'aria-describedby="plainHint"' in HTML
    assert 'id="plainHint"' in HTML
