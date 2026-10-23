"""FastAPI application: adapters + validation + rate limit + security headers.

Adapter-only: no business logic beyond wiring. Business logic lives in
planner.py / retrieval.py / prompting.py / the storage package, and the
response payloads are built by serializers.py.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint

from .config import settings
from .routes import router

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=str(settings.log_level).upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="Celebration & Event Planner", version="0.1.0")

# --- CORS (allowlist, never wildcard) ---
# An empty allowlist is safe: the CORS middleware then omits the
# Access-Control-Allow-Origin header and rejects preflights, so the browser
# blocks every cross-origin call.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Demo-Session"],
)

# --- Rate limit buckets ---
# Bounded LRU: buckets are refreshed on use and the least recently used
# (therefore stale) ones are evicted once the store exceeds its cap.
_RATE_WINDOW_SECONDS = 60.0
# Retry-After written when a client exceeds the rate limit.
RATE_LIMIT_RETRY_AFTER_SECONDS = 60
_rate_buckets: dict[str, list[float]] = {}

# --- Security headers ---
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    "font-src 'self'; object-src 'none'; frame-ancestors 'none'"
)
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=()"
REFERRER_POLICY = "strict-origin-when-cross-origin"
STRICT_TRANSPORT_SECURITY = "max-age=31536000; includeSubDomains"


def _evict_rate_buckets() -> None:
    """Bound the rate-limit bucket store by evicting idle clients.

    The store behaves as a bounded LRU: every request refreshes its bucket's
    position, and when more than ``settings.max_rate_buckets`` clients are
    tracked the least recently used (and therefore stale) buckets are
    dropped. Memory therefore stays flat under a flood of unique source
    addresses, while the sliding-window semantics for active clients are
    unchanged.

    Returns:
        None.
    """
    max_buckets = max(1, settings.max_rate_buckets)
    overflow = len(_rate_buckets) - max_buckets
    if overflow <= 0:
        return
    for ip in list(_rate_buckets)[:overflow]:
        _rate_buckets.pop(ip, None)


def _rate_limit(request: Request) -> None:
    """Apply per-IP rate limiting, raising 429 when exceeded.

    The bucket key is the transport-level client address
    (``request.client.host``). Proxy headers such as ``X-Forwarded-For`` are
    deliberately ignored: they are attacker-controlled, so trusting them
    would let a client rotate its identity to bypass the limit.

    Args:
        request: Incoming request whose client IP is used as the bucket key.

    Returns:
        None. Rate-limit metadata is stored on ``request.state``.

    Raises:
        HTTPException: With status 429 when the client exceeded its quota.
    """
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _rate_buckets.get(ip)
    if bucket is None:
        _evict_rate_buckets()
        bucket = _rate_buckets[ip] = []
    else:
        # Refresh recency so the LRU sweep evicts genuinely idle clients.
        del _rate_buckets[ip]
        _rate_buckets[ip] = bucket
    bucket[:] = [t for t in bucket if now - t < _RATE_WINDOW_SECONDS]
    limit = settings.rate_limit_per_min
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="rate limit exceeded, slow down")
    bucket.append(now)
    request.state.rate_limit_limit = limit
    request.state.rate_limit_remaining = max(0, limit - len(bucket))
    request.state.rate_limit_reset = int(now + _RATE_WINDOW_SECONDS)


def _attach_headers(
    resp: Response, request: Request, start: float, limited: bool = False,
) -> None:
    """Attach security and rate-limit headers to a response.

    This is the single place where response headers are written, so every
    response - success, 404, 422, static file, or 429 - carries exactly the
    same header set.

    Args:
        resp: Response whose headers are mutated in place.
        request: Request supplying the rate-limit metadata.
        start: Start timestamp used to compute the process-time header.
        limited: When True, the response is flagged as rate limited and
            remaining quota is reported as zero.

    Returns:
        None.
    """
    elapsed_ms = (time.perf_counter() - start) * 1000
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = REFERRER_POLICY
    resp.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    resp.headers["Permissions-Policy"] = PERMISSIONS_POLICY
    resp.headers["Strict-Transport-Security"] = STRICT_TRANSPORT_SECURITY
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Process-Time"] = f"{elapsed_ms / 1000:.3f}s"
    limit = getattr(request.state, "rate_limit_limit", settings.rate_limit_per_min)
    remaining = (
        0
        if limited
        else getattr(request.state, "rate_limit_remaining", settings.rate_limit_per_min)
    )
    reset = getattr(
        request.state, "rate_limit_reset", int(time.time() + _RATE_WINDOW_SECONDS),
    )
    resp.headers["X-RateLimit-Limit"] = str(limit)
    resp.headers["X-RateLimit-Remaining"] = str(remaining)
    resp.headers["X-RateLimit-Reset"] = str(reset)
    if limited:
        resp.headers["Retry-After"] = str(RATE_LIMIT_RETRY_AFTER_SECONDS)


@app.middleware("http")
async def security_headers(
    request: Request, call_next: RequestResponseEndpoint,
) -> Response:
    """Attach security headers and rate-limit info to every response.

    An unhandled downstream exception is converted into a bare 500 JSON
    response that still carries the full header set: Starlette's
    ``ServerErrorMiddleware`` sits outside this middleware and would
    otherwise emit a headerless 500, so the error path is handled here.

    Args:
        request: Incoming request being processed.
        call_next: Downstream handler producing the response.

    Returns:
        The response with security and rate-limit headers attached.
    """
    start = time.perf_counter()
    try:
        _rate_limit(request)
    except HTTPException as exc:
        resp = JSONResponse(status_code=429, content={"detail": exc.detail})
        _attach_headers(resp, request, start, limited=True)
        return resp

    try:
        response = await call_next(request)
    except Exception:  # noqa: BLE001
        # Logged server-side only; the client gets a bare 500 with headers.
        logger.exception(
            "unhandled error on %s %s", request.method, request.url.path,
        )
        response = JSONResponse(
            status_code=500, content={"detail": "Internal server error"},
        )
    _attach_headers(response, request, start)
    return response


app.include_router(router)

_STATIC_DIR = Path(__file__).resolve().parents[2] / "frontend"

try:
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
except Exception as exc:  # noqa: BLE001
    logger.warning("static files unavailable at %s (%s)", _STATIC_DIR, type(exc).__name__)
