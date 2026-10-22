"""Retrieval over a curated ideas corpus (TF-IDF, no model download).

Used to ground personalized ideas in a small, vetted knowledge base.
Strategy: cached TF-IDF primary, token-overlap fallback (zero-dep safe).

Caching: the corpus + vectorizer + matrix are built once and reused
(bounded memory, sub-second repeat queries).
"""

from __future__ import annotations

import json
import math
import re
import threading
from pathlib import Path

CORPUS_PATH = Path(__file__).resolve().parents[1] / "data" / "ideas_corpus.json"

_cache_lock = threading.Lock()
_cached: dict = {"corpus": None, "vectorizer": None, "matrix": None, "mtime": None}

# Fallback English stop-word set, used when scikit-learn is unavailable.
# The set mirrors the words sklearn removes, so the "no signal" guard below
# behaves identically in both environments.
_FALLBACK_STOP_WORDS = frozenset(
    {
        "a", "about", "above", "after", "again", "against", "all", "am", "an",
        "and", "any", "are", "as", "at", "be", "because", "been", "before",
        "being", "below", "between", "both", "but", "by", "can", "could",
        "did", "do", "does", "doing", "down", "during", "each", "few", "for",
        "from", "further", "had", "has", "have", "having", "he", "her", "here",
        "hers", "him", "his", "how", "i", "if", "in", "into", "is", "it",
        "its", "itself", "just", "me", "more", "most", "my", "no", "nor",
        "not", "now", "of", "off", "on", "once", "only", "or", "other", "our",
        "ours", "out", "over", "own", "same", "she", "should", "so", "some",
        "such", "than", "that", "the", "their", "theirs", "them", "then",
        "there", "these", "they", "this", "those", "through", "to", "too",
        "under", "until", "up", "very", "was", "we", "were", "what", "when",
        "where", "which", "while", "who", "whom", "why", "will", "with",
        "would", "you", "your", "yours",
    },
)

_stop_words_cache: frozenset[str] | None = None


def _stop_words() -> frozenset[str]:
    """Return the English stop-word set used to detect signal-free queries.

    Returns:
        sklearn's English stop words when scikit-learn is installed, else the
        built-in fallback set.
    """
    global _stop_words_cache
    if _stop_words_cache is None:
        try:
            from sklearn.feature_extraction.text import (  # type: ignore[import-untyped]
                ENGLISH_STOP_WORDS,
            )

            _stop_words_cache = frozenset(ENGLISH_STOP_WORDS)
        except Exception:  # noqa: BLE001
            _stop_words_cache = _FALLBACK_STOP_WORDS
    return _stop_words_cache


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric tokens.

    Args:
        text: Raw text to tokenize.

    Returns:
        The lowercase alphanumeric tokens found in the text.
    """
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def load_corpus() -> list[dict]:
    """Load the ideas corpus from disk.

    Returns:
        The parsed corpus entries, or an empty list when the file is missing
        or unreadable.
    """
    if not CORPUS_PATH.exists():
        return []
    try:
        return json.loads(CORPUS_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []


def _build_index(corpus: list[dict]) -> tuple:
    """Build (vectorizer, matrix) or (None, None) on failure.

    Args:
        corpus: Corpus entries used as the fitting documents.

    Returns:
        A ``(vectorizer, matrix)`` pair, or ``(None, None)`` when scikit-learn
        is unavailable or fitting fails.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]

        docs = [c.get("text", "") for c in corpus]
        vec = TfidfVectorizer(stop_words="english")
        matrix = vec.fit_transform(docs)
        return vec, matrix
    except Exception:  # noqa: BLE001
        return None, None


def _get_index(corpus: list[dict]) -> tuple:
    """Return cached (vectorizer, matrix, corpus), rebuilding if needed.

    Args:
        corpus: Corpus entries the cached index must correspond to.

    Returns:
        A ``(vectorizer, matrix, corpus)`` triple, refreshed whenever the
        corpus file or its contents change.
    """
    global _cached
    mtime = CORPUS_PATH.stat().st_mtime if CORPUS_PATH.exists() else None
    with _cache_lock:
        if (
            _cached["corpus"] is None
            or _cached["mtime"] != mtime
            or len(_cached["corpus"]) != len(corpus)
        ):
            vec, matrix = _build_index(corpus)
            _cached = {
                "corpus": list(corpus),
                "vectorizer": vec,
                "matrix": matrix,
                "mtime": mtime,
            }
        return _cached["vectorizer"], _cached["matrix"], _cached["corpus"]


def _has_signal(query: str) -> bool:
    """Report whether a query carries at least one meaningful term.

    A query built only from stop words ("the and of to") has no signal and
    must not ground an answer in incidental word overlap.

    Args:
        query: Free-text query to inspect.

    Returns:
        True when the query contains at least one non-stop-word token.
    """
    tokens = set(_tokenize(query))
    return bool(tokens - _stop_words())


def _rank_by_token_overlap(
    corpus: list[dict], query: str, top_k: int
) -> list[dict]:
    """Rank corpus entries by raw token overlap (zero-dependency fallback).

    Args:
        corpus: Corpus entries to rank.
        query: Free-text query whose tokens are matched against the corpus.
        top_k: Maximum number of entries to return.

    Returns:
        The best-matching corpus entries, each carrying a "score" key.
    """
    q_tokens = set(_tokenize(query))
    scored: list[dict] = []
    for c in corpus:
        c_tokens = set(_tokenize(c.get("text", "")))
        if not q_tokens or not c_tokens:
            continue
        overlap = len(q_tokens & c_tokens)
        if overlap == 0:
            continue
        score = overlap / math.sqrt(len(q_tokens) * len(c_tokens))
        entry = dict(c)
        entry["score"] = float(min(1.0, score))
        scored.append(entry)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def search(query: str, top_k: int = 5, event_type: str | None = None) -> list[dict]:
    """Return top_k corpus entries most relevant to query. Each has 'score' in (0,1].

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
    if event_type:
        corpus = [c for c in corpus if c.get("event_type") in (event_type, "all")]
    if not corpus:
        return []
    top_k = max(1, min(top_k, 10))

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]
        from sklearn.metrics.pairwise import cosine_similarity  # type: ignore[import-untyped]

        docs = [c.get("text", "") for c in corpus]
        v = TfidfVectorizer(stop_words="english")
        m = v.fit_transform(docs + [query])
        sims = cosine_similarity(m[-1], m[:-1]).flatten()
        ranked = sorted(enumerate(sims), key=lambda x: x[1], reverse=True)
        out = []
        for idx, score in ranked[:top_k]:
            if score <= 0:
                continue
            entry = dict(corpus[idx])
            entry["score"] = float(score)
            out.append(entry)
        if out:
            return out
    except Exception:  # noqa: BLE001, S110
        pass

    # Fallback: token overlap.
    return _rank_by_token_overlap(corpus, query, top_k)


def reset_cache() -> None:
    """Reset the cached retrieval index.

    Returns:
        None.
    """
    global _cached
    with _cache_lock:
        _cached = {"corpus": None, "vectorizer": None, "matrix": None, "mtime": None}
