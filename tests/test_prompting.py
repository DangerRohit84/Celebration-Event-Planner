"""Prompting tests."""

from __future__ import annotations

import re
from pathlib import Path

from backend.app.prompting import (
    CANNOT_DETERMINE,
    DISCLAIMER,
    DISCLAIMER_RULE,
    build_grounded_prompt,
    build_ideas_prompt,
    calibrate_confidence,
    confidence_for,
)

ROOT = Path(__file__).resolve().parents[1]
DOCS = (
    ROOT / "README.md",
    ROOT / "docs" / "NARRATIVE.md",
)

HITS = [{"id": "w1", "text": "garden ceremony"}]


def test_build_ideas_prompt():
    hits = [{"id": "w1", "text": "garden ceremony"}]
    p = build_ideas_prompt("ideas", hits, "wedding")
    assert "<context>" in p
    assert "<question>" in p
    assert "Cannot Determine" in p


def test_prompt_carries_the_disclaimer_rule():
    """Rule 3 must put the disclaimer into the model's answer."""
    prompt = build_ideas_prompt("ideas", HITS, "wedding")
    assert "Rule 3" in prompt
    assert "not professional advice" in prompt
    assert DISCLAIMER in prompt
    assert DISCLAIMER_RULE in prompt


def test_numbered_rule_count_matches_the_documentation():
    """The prompt's numbered rules must match the count the docs quote."""
    prompt = build_ideas_prompt("ideas", HITS, "wedding")
    rendered = re.findall(r"^Rule (\d+):", prompt, re.MULTILINE)
    assert rendered == ["1", "2", "3"]
    for document in DOCS:
        text = document.read_text(encoding="utf-8")
        match = re.search(r"Rules\s+1\s*[-–—]\s*(\d+)", text)
        assert match, f"{document.name} does not state the numbered rule count"
        assert int(match.group(1)) == len(rendered), (
            f"{document.name} quotes {match.group(1)} rules, the prompt has "
            f"{len(rendered)}"
        )


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
    assert "Rule 3" in p
