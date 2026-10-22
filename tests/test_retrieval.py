"""Retrieval tests."""

import inspect
import sys

import pytest

from backend.app import retrieval
from backend.app.retrieval import load_corpus, reset_cache, search


def test_search_returns_hits():
    hits = search("outdoor ceremony", top_k=3)
    assert isinstance(hits, list)


def test_search_scores():
    hits = search("outdoor ceremony lights", top_k=5)
    if hits:
        scores = [h.get("score", 0) for h in hits]
        assert all(0 < s <= 1.0 for s in scores)
        assert scores == sorted(scores, reverse=True)


def test_top_k_clamp():
    hits = search("ceremony", top_k=100)
    assert len(hits) <= 10


def test_event_type_filter():
    hits = search("cake", top_k=5, event_type="birthday")
    for h in hits:
        assert h.get("event_type") in ("birthday", "all")


def test_load_corpus():
    c = load_corpus()
    assert isinstance(c, list)
    assert len(c) > 0


def test_reset_cache_clears_the_index():
    """reset_cache() must drop the fitted index so the next search rebuilds it."""
    reset_cache()
    assert retrieval._cached["vectorizer"] is None
    assert retrieval._cached["matrix"] is None

    search("ceremony", top_k=2)
    assert retrieval._cached["vectorizer"] is not None
    assert retrieval._cached["matrix"] is not None

    reset_cache()
    assert retrieval._cached["vectorizer"] is None
    assert retrieval._cached["matrix"] is None


def test_index_is_reused_across_searches():
    """The fitted vectorizer must be reused, not rebuilt, between searches."""
    reset_cache()
    search("outdoor ceremony", top_k=3)
    first = retrieval._cached["vectorizer"]
    assert first is not None

    search("cake", top_k=3)
    search("catering", top_k=3)
    assert retrieval._cached["vectorizer"] is first


def test_vectorizer_is_constructed_only_once(monkeypatch):
    """Three searches must fit the vectorizer exactly once.

    The patched ``__init__`` keeps the original signature: scikit-learn
    introspects ``__init__`` to enumerate estimator parameters, and a
    ``(*args, **kwargs)`` stand-in would make every ``fit`` fail.
    """
    sklearn_text = pytest.importorskip("sklearn.feature_extraction.text")
    vectorizer_cls = sklearn_text.TfidfVectorizer
    original_init = vectorizer_cls.__init__
    constructions: list[object] = []

    def counting_init(self, *args, **kwargs):
        constructions.append(self)
        return original_init(self, *args, **kwargs)

    counting_init.__signature__ = inspect.signature(original_init)
    monkeypatch.setattr(vectorizer_cls, "__init__", counting_init)

    reset_cache()
    for _ in range(3):
        search("outdoor ceremony ideas", top_k=3)

    assert len(constructions) == 1, "the TF-IDF vectorizer was rebuilt per request"
    assert retrieval._cached["vectorizer"] is not None


def test_event_type_filter_does_not_refit_the_index(monkeypatch):
    """Filtering by event type must not trigger a refit of the index."""
    sklearn_text = pytest.importorskip("sklearn.feature_extraction.text")
    vectorizer_cls = sklearn_text.TfidfVectorizer
    original_init = vectorizer_cls.__init__
    constructions: list[object] = []

    def counting_init(self, *args, **kwargs):
        constructions.append(self)
        return original_init(self, *args, **kwargs)

    counting_init.__signature__ = inspect.signature(original_init)
    monkeypatch.setattr(vectorizer_cls, "__init__", counting_init)

    reset_cache()
    search("outdoor ceremony", top_k=5, event_type="wedding")
    assert len(constructions) == 1
    search("cake", top_k=5, event_type="birthday")
    assert len(constructions) == 1


def test_scores_are_comparable_across_queries():
    """The cached index keeps the IDF scale stable between queries."""
    reset_cache()
    first = search("outdoor ceremony", top_k=3)
    second = search("decor flowers", top_k=3)
    assert first and second
    # Both queries are scored against the same fitted matrix, so a repeated
    # query returns exactly the same score.
    repeat = search("outdoor ceremony", top_k=3)
    assert [h["score"] for h in first] == [h["score"] for h in repeat]


# --------------------------------------------------------------------------
# The scikit-learn-free fallback must behave like the scikit-learn path.
# --------------------------------------------------------------------------

# Queries whose tokens are all stop words or that contain a stop word the
# scikit-learn list removes and a partial list would keep ("everyone",
# "per"). A fallback list that is not the complete scikit-learn list makes
# one of these two paths ground and the other refuse.
PROBE_IN_DOMAIN = [
    "outdoor ceremony ideas",
    "budget-friendly decor ideas for a garden wedding",
    "photo booth props and instant prints",
    "digital invitations 6 weeks ahead with RSVP tracking",
    "day-of timeline shared with all vendors",
    "guest favor and entertainment",
    "buffet with live stations",
    "seasonal flowers and string lights",
    "rsvp tracking and dietary capture",
    "cake",
    "catering",
    "decor flowers",
    "cake for everyone",
    "timelines and vendors per day",
]

PROBE_OUT_OF_DOMAIN = [
    "what is the capital of France?",
    "quantum mechanical supercomputing",
    "the and of to",
    "best honeymoon destination in Maldives",
    "stock market tips for 2026",
    "everyone invited",
]

PROBE_QUERIES = PROBE_IN_DOMAIN + PROBE_OUT_OF_DOMAIN


def test_fallback_stop_words_match_sklearn():
    """The hard-coded fallback set must be scikit-learn's list, in full."""
    text = pytest.importorskip("sklearn.feature_extraction.text")
    sklearn_words = set(text.ENGLISH_STOP_WORDS)
    fallback = set(retrieval._FALLBACK_STOP_WORDS)
    assert fallback == sklearn_words, (
        "fallback stop-word set has drifted from sklearn: "
        f"only-fallback={sorted(fallback - sklearn_words)} "
        f"only-sklearn={sorted(sklearn_words - fallback)}"
    )
    assert len(fallback) == 318


def test_fallback_path_returns_the_same_hit_counts_as_sklearn(monkeypatch):
    """Blocking scikit-learn must not change how many hits a query returns.

    The fallback ranker and the TF-IDF ranker are different algorithms, so
    the guarantee under test is the one the docs make: the same number of
    corpus entries is matched either way, including none at all for an
    out-of-domain question.
    """
    pytest.importorskip("sklearn.feature_extraction.text")
    monkeypatch.setattr(retrieval, "_stop_words_cache", None)
    reset_cache()
    with_sklearn = {q: len(search(q, top_k=5)) for q in PROBE_QUERIES}

    # Simulate a deployment without scikit-learn.
    monkeypatch.setitem(sys.modules, "sklearn.feature_extraction.text", None)
    monkeypatch.setitem(sys.modules, "sklearn.metrics.pairwise", None)
    monkeypatch.setattr(retrieval, "_stop_words_cache", None)
    reset_cache()
    without_sklearn = {q: len(search(q, top_k=5)) for q in PROBE_QUERIES}

    assert without_sklearn == with_sklearn, (
        "the fallback path and the scikit-learn path disagree: "
        f"sklearn={with_sklearn} fallback={without_sklearn}"
    )
    # The out-of-domain questions must refuse on both paths.
    for query in PROBE_OUT_OF_DOMAIN:
        assert with_sklearn[query] == 0
        assert without_sklearn[query] == 0
    # And an in-domain question must still ground on both paths.
    for query in PROBE_IN_DOMAIN:
        assert with_sklearn[query] > 0, f"{query!r} stopped grounding"
        assert without_sklearn[query] > 0, f"{query!r} stopped grounding"
