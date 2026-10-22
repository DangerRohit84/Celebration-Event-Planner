"""FastAPI application: adapters + validation + rate limit + session isolation.

Adapter-only: no business logic beyond wiring. Business logic lives in
planner.py / retrieval.py / prompting.py / storage.py.
"""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import settings
from .routes import router

app = FastAPI(title="Celebration & Event Planner", version="0.1.0")

# --- CORS (allowlist, never wildcard) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Demo-Session"],
)

# --- Rate limit buckets ---
_rate_buckets: dict[str, list[float]] = {}
_RATE_BUCKETS = _rate_buckets


def _rate_limit(request: Request) -> None:
    """Apply per-IP rate limiting, raising 429 when exceeded."""
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = 60.0
    bucket = _rate_buckets.setdefault(ip, [])
    bucket[:] = [t for t in bucket if now - t < window]
    limit = settings.rate_limit_per_min
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="rate limit exceeded, slow down")
    bucket.append(now)
    request.state.rate_limit_limit = limit
    request.state.rate_limit_remaining = max(0, limit - len(bucket))
    request.state.rate_limit_reset = int(now + window)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    """Attach security headers and rate-limit info to responses."""
    start = time.perf_counter()
    try:
        _rate_limit(request)
    except HTTPException as e:
        request.state._rate_limited = True
        request.state._rate_exc = e
    if getattr(request.state, "_rate_limited", False):
        exc = request.state._rate_exc
        resp = JSONResponse(status_code=429, content={"detail": exc.detail})
        _attach_headers(resp, request, start, limited=True)
        return resp

    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; object-src 'none'; frame-ancestors 'none'"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Process-Time"] = f"{elapsed:.2f}ms" if False else f"{elapsed/1000:.3f}s"
    limit = getattr(request.state, "rate_limit_limit", settings.rate_limit_per_min)
    remaining = getattr(request.state, "rate_limit_remaining", settings.rate_limit_per_min)
    reset = getattr(request.state, "rate_limit_reset", int(time.time() + 60))
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset)
    return response


def _attach_headers(resp, request, start, limited: bool = False) -> None:
    """Attach security + rate-limit headers to a response."""
    elapsed = (time.perf_counter() - start) * 1000
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = "default-src 'self'; object-src 'none'; frame-ancestors 'none'"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Process-Time"] = f"{elapsed/1000:.3f}s"
    limit = getattr(request.state, "rate_limit_limit", settings.rate_limit_per_min)
    remaining = 0 if limited else getattr(request.state, "rate_limit_remaining", settings.rate_limit_per_min)
    reset = getattr(request.state, "rate_limit_reset", int(time.time() + 60))
    resp.headers["X-RateLimit-Limit"] = str(limit)
    resp.headers["X-RateLimit-Remaining"] = str(remaining)
    resp.headers["X-RateLimit-Reset"] = str(reset)
    if limited:
        resp.headers["Retry-After"] = "60"


app.include_router(router)

try:
    app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parents[2] / "frontend")), name="static")
except Exception:  # noqa: BLE001, S110
    pass
