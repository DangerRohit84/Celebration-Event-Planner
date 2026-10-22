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


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric tokens."""
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def load_corpus() -> list[dict]:
    """Load the ideas corpus from disk."""
    if not CORPUS_PATH.exists():
        return []
    try:
        return json.loads(CORPUS_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []


def _build_index(corpus: list[dict]) -> tuple:
    """Build (vectorizer, matrix) or (None, None) on failure."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]

        docs = [c.get("text", "") for c in corpus]
        vec = TfidfVectorizer(stop_words="english")
        matrix = vec.fit_transform(docs)
        return vec, matrix
    except Exception:  # noqa: BLE001
        return None, None


def _get_index(corpus: list[dict]) -> tuple:
    """Return cached (vectorizer, matrix, corpus), rebuilding if needed."""
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


def search(query: str, top_k: int = 5, event_type: str | None = None) -> list[dict]:
    """Return top_k corpus entries most relevant to query. Each has 'score' in (0,1]."""
    corpus = load_corpus()
    if event_type:
        corpus = [c for c in corpus if c.get("event_type") in (event_type, "all")]
    if not corpus:
        return []
    top_k = max(1, min(top_k, 10))

    _get_index(load_corpus())
    # filter cached index to event_type subset
    # Rebuild subset index lazily (small corpus) for correctness.
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
    q_tokens = set(_tokenize(query))
    scored = []
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


def reset_cache() -> None:
    """Reset the cached retrieval index."""
    global _cached
    with _cache_lock:
        _cached = {"corpus": None, "vectorizer": None, "matrix": None, "mtime": None}
