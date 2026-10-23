"""Shared route dependencies: retry-after constants and event-type parsing."""

from __future__ import annotations

from ..models import EventType

# Retry-After written when the bounded event store is full.
STORE_FULL_RETRY_AFTER_SECONDS = 30
# Retry-After written when the bounded session document store is full.
DOCUMENT_STORE_FULL_RETRY_AFTER_SECONDS = 30


def _parse_event_type(value: str) -> EventType:
    """Parse an event type string, defaulting to OTHER.
    Args:
        value: Raw event type identifier from the client.
    Returns:
        The matching event type, or EventType.OTHER for unknown values.
    """
    try:
        return EventType(value)
    except ValueError:
        return EventType.OTHER
