"""Score-calibrated confidence for grounded answers.

The score of the best retrieved entry decides between "Grounded" and
"Partial"; when no entry carries a usable score the number of hits decides
instead, so a retrieval that cannot be scored is still reported honestly
rather than being silently downgraded. Zero hits always refuse.
"""

from __future__ import annotations


def _hit_score(hit: object) -> float:
    """Read the similarity score of a retrieved entry.

    Corpus hits are dictionaries; document chunks are objects with a
    ``score`` attribute. Both shapes are supported so one calibration
    function can serve every caller.

    Args:
        hit: The retrieved entry to read.

    Returns:
        The similarity score, or 0.0 when the entry carries none.
    """
    if isinstance(hit, dict):
        try:
            return float(hit.get("score", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(getattr(hit, "score", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def calibrate_confidence(hits: list[dict]) -> str:
    """Calibrate a confidence label from retrieved hits.

    Args:
        hits: Retrieved corpus entries carrying similarity scores.

    Returns:
        "Grounded", "Partial", or "Cannot Determine".
    """
    return confidence_for(hits)


def confidence_for(
    hits: list, count: int = 0, scores: list[float] | None = None,
) -> str:
    """Score-calibrated confidence with a count fallback.

    Args:
        hits: Retrieved entries whose scores are read when ``scores`` is absent.
        count: Optional explicit hit count used when scores are unavailable.
        scores: Optional pre-computed similarity scores for the hits.

    Returns:
        "Grounded", "Partial", or "Cannot Determine".
    """
    if not hits:
        return "Cannot Determine"
    if scores is None:
        scores = [_hit_score(hit) for hit in hits]
    if not scores or all(s == 0 for s in scores):
        # No usable score: fall back to how many entries were retrieved.
        n = count if count else len(hits)
        if n <= 0:
            return "Cannot Determine"
        if n >= 2:
            return "Grounded"
        return "Partial"
    mx = max(scores)
    n = count if count else len(hits)
    if mx >= 0.18 and n >= 2:
        return "Grounded"
    return "Partial"
