"""Answer generation: provider calls with deterministic degradation."""

from __future__ import annotations

import logging

from ..config import settings
from ..ingest import get_document_store, relevant_chunks
from ..llm import build_provider
from ..prompting import render_grounded_ideas

logger = logging.getLogger(__name__)


def _generate_answer(
    prompt: str, hits: list[dict], plain_language: bool = False,
) -> str:
    """Answer a grounded prompt, degrading safely when the provider fails.
    Args:
        prompt: Fully rendered prompt to send to the provider.
        hits: Retrieved corpus entries backing the grounded fallback.
        plain_language: When True, the provider is asked for short,
            jargon-free sentences.
    Returns:
        The provider's answer, or a deterministic grounded answer derived from
        the retrieved hits.
    """
    try:
        return build_provider().answer(prompt, plain_language=plain_language)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "LLM provider '%s' failed (%s); degrading to the echo provider",
            settings.llm_provider,
            type(exc).__name__,
        )
    try:
        return build_provider("echo").answer(prompt, plain_language=plain_language)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Echo provider failed (%s); using the inline grounded fallback",
            type(exc).__name__,
        )
    return render_grounded_ideas(hits, plain_language=plain_language)


def _document_context(query: str) -> list[str]:
    """Return excerpts from the session document that match the query.
    Args:
        query: The user's question.
    Returns:
        The matching chunk texts, or an empty list when no document has been
        uploaded or nothing in it matches the query.
    """
    document = get_document_store().latest()
    if document is None:
        return []
    return relevant_chunks(document, query)
