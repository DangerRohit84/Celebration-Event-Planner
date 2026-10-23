"""Answer serializers: retrieved hits -> citations and idea strings.

Used by the ideas/ask flow to turn retrieval results into the wire format
of the answer payload. Pure functions, no I/O.
"""

from __future__ import annotations


def citation_dict(hit: dict) -> dict:
    """Serialize a retrieved corpus entry as a citation.

    Args:
        hit: Retrieved corpus entry carrying "id", "text", and "score".

    Returns:
        A mapping with the source identifier, the quoted text, and the
        similarity score.
    """
    return {
        "id": str(hit.get("id") or ""),
        "text": str(hit.get("text") or ""),
        "score": float(hit.get("score") or 0.0),
    }


def citation_dicts(hits: list[dict]) -> list[dict]:
    """Serialize retrieved corpus entries as a list of citations.

    Args:
        hits: Retrieved corpus entries backing the answer.

    Returns:
        One citation mapping per retrieved entry, in retrieval order.
    """
    return [citation_dict(hit) for hit in hits]


def idea_texts(hits: list[dict]) -> list[str]:
    """Serialize retrieved corpus entries as a list of idea strings.

    Args:
        hits: Retrieved corpus entries backing the answer.

    Returns:
        The text of every retrieved entry, in retrieval order.
    """
    return [str(hit.get("text") or "") for hit in hits]
