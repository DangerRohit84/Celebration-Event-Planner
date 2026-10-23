"""Section-aware text chunking for extracted document text.

A chunk is a coherent passage, not a fixed-size slice of arbitrary
characters: text is first split into labelled sections at heading-like
lines, then each section is split on sentence boundaries and accumulated
up to a character budget. A single sentence longer than the budget is
hard-split, because there is no sentence boundary inside it to preserve.

The module is pure text processing: no I/O, no parsing, no HTTP.
"""

from __future__ import annotations

import re

# Sentence boundary: a terminator followed by whitespace.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

DEFAULT_CHUNK_CHARS = 800


def _is_heading(line: str) -> bool:
    """Report whether a line looks like a section heading.

    A heading is a short line that is not a sentence and is written in
    Title Case or ALL CAPS - the two conventions used by the event-planning
    documents this app accepts.

    Args:
        line: A single stripped line of extracted document text.

    Returns:
        True when the line should be treated as a section boundary.
    """
    if not line or len(line) > 80:
        return False
    if line.endswith((".", ",", ";", ":", "!", "?")):
        return False
    words = line.split()
    if not words or len(words) > 12:
        return False
    return line == line.title() or line == line.upper()


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split extracted text into labelled sections.

    A section starts at a heading-like line and runs until the next heading
    or a blank line. Sections without a heading are labelled with an empty
    string.

    Args:
        text: Extracted text of one page.

    Returns:
        A list of ``(section_label, section_body)`` pairs in document order.
    """
    sections: list[tuple[str, str]] = []
    label = ""
    body: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if body:
                sections.append((label, " ".join(body).strip()))
            body.clear()
            label = ""
            continue
        if _is_heading(line):
            if body:
                sections.append((label, " ".join(body).strip()))
                body.clear()
            elif label:
                # A heading with no body of its own still carries content.
                sections.append((label, label))
            label = line
            continue
        body.append(line)
    if body:
        sections.append((label, " ".join(body).strip()))
    elif label:
        sections.append((label, label))
    return sections


def _chunk_section(body: str, max_chars: int) -> list[str]:
    """Split one section into chunks that end on sentence boundaries.

    Sentences are accumulated until the chunk would exceed ``max_chars``.
    A single sentence longer than the limit is hard-split, because there is
    no sentence boundary inside it to preserve.

    Args:
        body: The text of a single section.
        max_chars: Maximum number of characters per chunk.

    Returns:
        The chunk texts produced from the section.
    """
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(body) if s.strip()]
    if not sentences:
        return []
    chunks: list[str] = []
    buffer = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            for start in range(0, len(sentence), max_chars):
                chunks.append(sentence[start : start + max_chars])
            continue
        if not buffer:
            buffer = sentence
        elif len(buffer) + 1 + len(sentence) <= max_chars:
            buffer = f"{buffer} {sentence}"
        else:
            chunks.append(buffer)
            buffer = sentence
    if buffer:
        chunks.append(buffer)
    return chunks


def chunk_text(text: str, *, max_chars: int = DEFAULT_CHUNK_CHARS) -> list[str]:
    """Split plain text into section-aware chunks.

    Args:
        text: The text to split.
        max_chars: Maximum number of characters per chunk.

    Returns:
        The chunk texts, in document order.
    """
    chunks: list[str] = []
    for _label, body in _split_sections(text):
        chunks.extend(_chunk_section(body, max_chars))
    return chunks
