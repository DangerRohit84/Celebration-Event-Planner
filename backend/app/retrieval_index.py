"""Cached TF-IDF index over the ideas corpus.

Caching: the corpus + vectorizer + matrix are built once over the FULL
corpus and reused. Every request only *transforms* the query with the
cached vectorizer, so the IDF weights stay stable across queries and
scores are comparable between them. The cache is invalidated when the
corpus file changes (mtime) or its length changes.

The cache dictionary is mutated in place (never rebound) so that module
attributes re-exporting it observe the same live object.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

CORPUS_PATH = Path(__file__).resolve().parents[1] / "data" / "ideas_corpus.json"

_cache_lock = threading.Lock()
_cached: dict = {"corpus": None, "vectorizer": None, "matrix": None, "mtime": None}


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

    The vectorizer is fitted on the corpus only - never on the query - so
    the resulting IDF weights depend on the corpus and not on the request.

    Args:
        corpus: Corpus entries used as the fitting documents.

    Returns:
        A ``(vectorizer, matrix)`` pair, or ``(None, None)`` when scikit-learn
        is unavailable or fitting fails.
    """
    try:
        from sklearn.feature_extraction.text import (
            TfidfVectorizer,  # type: ignore[import-untyped]
        )

        docs = [c.get("text", "") for c in corpus]
        vec = TfidfVectorizer(stop_words="english")
        matrix = vec.fit_transform(docs)
        return vec, matrix
    except Exception:  # noqa: BLE001
        return None, None


def _get_index(corpus: list[dict]) -> tuple:
    """Return cached (vectorizer, matrix, corpus), rebuilding if needed.

    The cache key is the corpus file's modification time plus its length:
    whenever either changes the index is rebuilt, otherwise the fitted
    vectorizer and matrix are reused.

    Args:
        corpus: Corpus entries the cached index must correspond to.

    Returns:
        A ``(vectorizer, matrix, corpus)`` triple, refreshed whenever the
        corpus file or its contents change.
    """
    mtime = CORPUS_PATH.stat().st_mtime if CORPUS_PATH.exists() else None
    with _cache_lock:
        if (
            _cached["corpus"] is None
            or _cached["mtime"] != mtime
            or len(_cached["corpus"]) != len(corpus)
        ):
            vec, matrix = _build_index(corpus)
            _cached.update(
                {
                    "corpus": list(corpus),
                    "vectorizer": vec,
                    "matrix": matrix,
                    "mtime": mtime,
                }
            )
        return _cached["vectorizer"], _cached["matrix"], _cached["corpus"]


def reset_cache() -> None:
    """Reset the cached retrieval index.

    Returns:
        None.
    """
    with _cache_lock:
        _cached.update(
            {"corpus": None, "vectorizer": None, "matrix": None, "mtime": None}
        )
