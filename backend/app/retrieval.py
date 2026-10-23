"""Retrieval over a curated ideas corpus (TF-IDF, no model download).

Used to ground personalized ideas in a small, vetted knowledge base.
Strategy: cached TF-IDF primary, token-overlap fallback (zero-dep safe).

The cached index lives in :mod:`backend.app.retrieval_index` and the
zero-dependency fallback (stop words + token-overlap ranking) lives in
:mod:`backend.app.retrieval_fallback`; both are re-exported here so the
historical import path keeps working.
"""

from __future__ import annotations

from .retrieval_fallback import _FALLBACK_STOP_WORDS as _FALLBACK_STOP_WORDS
from .retrieval_fallback import _has_signal, _rank_by_token_overlap
from .retrieval_index import _cached as _cached
from .retrieval_index import _get_index
from .retrieval_index import load_corpus as load_corpus
from .retrieval_index import reset_cache as reset_cache


def _rank_by_tf_idf(
    vectorizer: object,
    matrix: object,
    indexed: list[dict],
    query: str,
    top_k: int,
    event_type: str | None,
) -> list[dict]:
    """Score the cached index against a query and filter by event type.

    The query is only *transformed* with the already-fitted vectorizer, so
    no model is rebuilt per request and the IDF weights stay stable. The
    event-type filter is applied to the ranked results, not to the corpus
    that was fitted, so filtering never changes the scoring scale.

    Args:
        vectorizer: The fitted ``TfidfVectorizer`` from the cached index.
        matrix: The fitted sparse document-term matrix from the cached index.
        indexed: Corpus entries the matrix rows correspond to.
        query: Free-text query to score against the corpus.
        top_k: Maximum number of entries to return.
        event_type: Optional event type filter; entries tagged "all" always
            match.

    Returns:
        The best-matching corpus entries, each carrying a "score" key. An
        empty list when nothing matches.
    """
    from sklearn.metrics.pairwise import (
        cosine_similarity,  # type: ignore[import-untyped]
    )

    query_vector = vectorizer.transform([query])  # type: ignore[attr-defined]
    sims = cosine_similarity(query_vector, matrix).flatten()
    ranked = sorted(
        zip(indexed, (float(s) for s in sims), strict=False),
        key=lambda pair: pair[1],
        reverse=True,
    )
    out: list[dict] = []
    for entry, score in ranked:
        if score <= 0:
            continue
        if event_type and entry.get("event_type") not in (event_type, "all"):
            continue
        item = dict(entry)
        item["score"] = score
        out.append(item)
        if len(out) >= top_k:
            break
    return out


def search(query: str, top_k: int = 5, event_type: str | None = None) -> list[dict]:
    """Return top_k corpus entries most relevant to query. Each has 'score' in (0,1].

    The TF-IDF index is built once over the full corpus and cached; every
    call only transforms the query, so repeated searches are cheap and the
    resulting scores are comparable across queries. When scikit-learn is
    unavailable the token-overlap ranker is used instead.

    Args:
        query: Free-text query to match against the corpus.
        top_k: Maximum number of entries to return, clamped to 1..10.
        event_type: Optional event type filter; entries tagged "all" always match.

    Returns:
        The most relevant corpus entries, each carrying a "score" key.
    """
    if not _has_signal(query):
        # A query made only of stop words carries no signal: refuse rather
        # than grounding the answer in incidental word overlap.
        return []
    corpus = load_corpus()
    if not corpus:
        return []
    top_k = max(1, min(top_k, 10))

    vectorizer, matrix, indexed = _get_index(corpus)
    if vectorizer is not None and matrix is not None:
        try:
            hits = _rank_by_tf_idf(
                vectorizer, matrix, indexed, query, top_k, event_type,
            )
            if hits:
                return hits
        except Exception:  # noqa: BLE001, S110
            pass

    # Fallback: token overlap over the event-type-filtered corpus.
    filtered = corpus
    if event_type:
        filtered = [c for c in corpus if c.get("event_type") in (event_type, "all")]
    return _rank_by_token_overlap(filtered, query, top_k)
