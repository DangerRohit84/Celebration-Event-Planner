"""Retrieval tests."""
from backend.app.retrieval import search, load_corpus, reset_cache


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


def test_reset_cache():
    reset_cache()
    hits = search("ceremony", top_k=2)
    assert isinstance(hits, list)
