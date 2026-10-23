"""API routes package: thin Interface Adapters grouped by responsibility.

Each submodule owns one endpoint family and exposes its own ``router``;
this package merges them while preserving the original OpenAPI order.
"""

from __future__ import annotations

from fastapi import APIRouter

from . import event_updates, events, export, ideas, system, uploads

router = APIRouter()
router.include_router(system.router)
router.include_router(events.router)
router.include_router(event_updates.router)
router.include_router(ideas.router)
router.include_router(export.router)
router.include_router(uploads.router)
