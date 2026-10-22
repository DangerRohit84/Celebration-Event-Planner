"""Prompting tests."""

from backend.app.prompting import (
    CANNOT_DETERMINE,
    DISCLAIMER,
    build_grounded_prompt,
    build_ideas_prompt,
    calibrate_confidence,
    confidence_for,
)


def test_build_ideas_prompt():
    hits = [{"id": "w1", "text": "garden ceremony"}]
    p = build_ideas_prompt("ideas", hits, "wedding")
    assert "<context>" in p
    assert "<question>" in p
    assert "Cannot Determine" in p


def test_calibrate_confidence():
    assert calibrate_confidence([]) == "Cannot Determine"
    hits = [{"score": 0.5}, {"score": 0.3}]
    assert calibrate_confidence(hits) in ("Grounded", "Partial")


def test_confidence_for():
    assert confidence_for([], 0) == "Cannot Determine"
    from backend.app.models import Chunk

    c = [Chunk("a", "d", 1, "Clause 1", "x")]
    assert confidence_for(c, 1) in ("Partial", "Grounded")


def test_constants():
    assert "Cannot Determine" in CANNOT_DETERMINE
    assert "professional advice" in DISCLAIMER or "General" in DISCLAIMER


def test_build_grounded_prompt():
    hits = [{"id": "w1", "text": "garden"}]
    p = build_grounded_prompt("q", hits)
    assert "<context>" in p
