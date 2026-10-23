"""Deterministic answer rendering for grounded ideas.

Used as the last-resort fallback when every LLM provider is unavailable,
so the user still receives corpus-backed guidance instead of an error.
The plain-language rendering drops source markers and parentheticals and
cuts each entry to its first short clause, so it is genuinely shorter
than the standard rendering without inventing new content.
"""

from __future__ import annotations

import re

from .prompt_constants import CANNOT_DETERMINE, PLAIN_HEADER, STANDARD_HEADER

# A leading bracketed source marker, e.g. "[w1] ".
_CITATION_MARKER = re.compile(r"^\[[^\]]*\]\s*")
# A parenthetical aside, e.g. "(pasta, chaat)".
_PARENTHETICAL = re.compile(r"\s*\([^)]*\)")
# Maximum number of words kept in a plain-language sentence.
_PLAIN_MAX_WORDS = 14


def plain_sentence(text: str) -> str:
    """Reduce a corpus entry to its first short, plain sentence.

    A leading bracketed source marker is dropped, a parenthetical aside is
    removed, the sentence is cut at the first clause boundary and capped at
    a readable length. Together with the shorter plain header and the
    dropped source markers this keeps the plain-language rendering
    genuinely shorter than the standard one without inventing new content.

    Args:
        text: Raw corpus entry text, optionally prefixed with a source id.

    Returns:
        A shortened, jargon-light rendering of the first clause.
    """
    stripped = _CITATION_MARKER.sub("", text or "").strip()
    stripped = _PARENTHETICAL.sub("", stripped).strip()
    first = stripped.split(". ")[0].strip()
    for separator in (", ", "; ", ": "):
        if separator in first:
            first = first.split(separator)[0].strip()
            break
    words = first.split()
    if len(words) > _PLAIN_MAX_WORDS:
        first = " ".join(words[:_PLAIN_MAX_WORDS])
    return first.rstrip(".,;:")


def render_grounded_ideas(hits: list[dict], plain_language: bool = False) -> str:
    """Render a deterministic, grounded answer straight from retrieved hits.

    Args:
        hits: Retrieved corpus entries carrying "id" and "text" keys.
        plain_language: When True, the entries are rendered as short,
            jargon-free sentences without their bracketed source markers, so
            the whole rendering is shorter than the standard one.

    Returns:
        A bullet list of the retrieved entries, or the "Cannot Determine"
        notice when nothing was retrieved.
    """
    if not hits:
        return CANNOT_DETERMINE
    if plain_language:
        lines = [f"- {plain_sentence(str(h.get('text', '')))}" for h in hits[:5]]
        return PLAIN_HEADER + "\n" + "\n".join(lines)
    lines = [f"- [{h.get('id')}] {h.get('text', '')}" for h in hits[:5]]
    return STANDARD_HEADER + "\n" + "\n".join(lines)
