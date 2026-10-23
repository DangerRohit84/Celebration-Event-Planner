"""Zero-dependency retrieval fallback: stop words + token-overlap ranking.

Used when scikit-learn is unavailable, and by the signal guard that keeps
stop-word-only queries from grounding an answer in incidental overlap.

The fallback stop-word list is the COMPLETE scikit-learn
``ENGLISH_STOP_WORDS`` list (318 entries), copied verbatim so that a
scikit-learn-free deployment removes exactly the same words as the TF-IDF
path. Both the list and the retrieval behaviour it guards are therefore
identical in the two environments - the "no signal" guard and the
token-overlap ranker agree with ``TfidfVectorizer(stop_words="english")``
token for token.

``tests/test_retrieval.py::test_fallback_stop_words_match_sklearn`` pins
this equality against the installed scikit-learn, so the copy cannot
silently drift away from the upstream list.
"""

from __future__ import annotations

import math
import re

_FALLBACK_STOP_WORDS = frozenset(
    {
        "a", "about", "above", "across", "after", "afterwards", "again", "against", "all", "almost", "alone", "along",
        "already", "also", "although", "always", "am", "among", "amongst", "amoungst", "amount", "an", "and", "another",
        "any", "anyhow", "anyone", "anything", "anyway", "anywhere", "are", "around", "as", "at", "back", "be",
        "became", "because", "become", "becomes", "becoming", "been", "before", "beforehand", "behind", "being", "below", "beside",
        "besides", "between", "beyond", "bill", "both", "bottom", "but", "by", "call", "can", "cannot", "cant",
        "co", "con", "could", "couldnt", "cry", "de", "describe", "detail", "do", "done", "down", "due",
        "during", "each", "eg", "eight", "either", "eleven", "else", "elsewhere", "empty", "enough", "etc", "even",
        "ever", "every", "everyone", "everything", "everywhere", "except", "few", "fifteen", "fifty", "fill", "find", "fire",
        "first", "five", "for", "former", "formerly", "forty", "found", "four", "from", "front", "full", "further",
        "get", "give", "go", "had", "has", "hasnt", "have", "he", "hence", "her", "here", "hereafter",
        "hereby", "herein", "hereupon", "hers", "herself", "him", "himself", "his", "how", "however", "hundred", "i",
        "ie", "if", "in", "inc", "indeed", "interest", "into", "is", "it", "its", "itself", "keep",
        "last", "latter", "latterly", "least", "less", "ltd", "made", "many", "may", "me", "meanwhile", "might",
        "mill", "mine", "more", "moreover", "most", "mostly", "move", "much", "must", "my", "myself", "name",
        "namely", "neither", "never", "nevertheless", "next", "nine", "no", "nobody", "none", "noone", "nor", "not",
        "nothing", "now", "nowhere", "of", "off", "often", "on", "once", "one", "only", "onto", "or",
        "other", "others", "otherwise", "our", "ours", "ourselves", "out", "over", "own", "part", "per", "perhaps",
        "please", "put", "rather", "re", "same", "see", "seem", "seemed", "seeming", "seems", "serious", "several",
        "she", "should", "show", "side", "since", "sincere", "six", "sixty", "so", "some", "somehow", "someone",
        "something", "sometime", "sometimes", "somewhere", "still", "such", "system", "take", "ten", "than", "that", "the",
        "their", "them", "themselves", "then", "thence", "there", "thereafter", "thereby", "therefore", "therein", "thereupon", "these",
        "they", "thick", "thin", "third", "this", "those", "though", "three", "through", "throughout", "thru", "thus",
        "to", "together", "too", "top", "toward", "towards", "twelve", "twenty", "two", "un", "under", "until",
        "up", "upon", "us", "very", "via", "was", "we", "well", "were", "what", "whatever", "when",
        "whence", "whenever", "where", "whereafter", "whereas", "whereby", "wherein", "whereupon", "wherever", "whether", "which", "while",
        "whither", "who", "whoever", "whole", "whom", "whose", "why", "will", "with", "within", "without", "would",
        "yet", "you", "your", "yours", "yourself", "yourselves",
    }
)

_stop_words_cache: frozenset[str] | None = None


def _stop_words() -> frozenset[str]:
    """Return the English stop-word set used to detect signal-free queries.

    Returns:
        sklearn's English stop words when scikit-learn is installed, else the
        built-in fallback set. The two sets are identical, so the signal
        guard and the token-overlap ranker behave the same either way.
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

    Stop words are removed from both sides before the overlap is measured,
    exactly as the TF-IDF path does (``stop_words="english"``). Without
    that, an unrelated question such as "what is the capital of France"
    would match a corpus entry on the word "of" and produce a confident,
    meaningless answer instead of the hard refusal the docs promise.

    Args:
        corpus: Corpus entries to rank.
        query: Free-text query whose tokens are matched against the corpus.
        top_k: Maximum number of entries to return.

    Returns:
        The best-matching corpus entries, each carrying a "score" key.
    """
    stop_words = _stop_words()
    q_tokens = set(_tokenize(query)) - stop_words
    scored: list[dict] = []
    for c in corpus:
        c_tokens = set(_tokenize(c.get("text", ""))) - stop_words
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
