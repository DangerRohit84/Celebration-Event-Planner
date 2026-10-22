# Deployment — any host works, Cloud Run suggested for Google bonus

MVP is a single FastAPI app serving API + static frontend. No build step, no disk writes beyond SQLite.

## Option A: Cloud Run (bonus + easiest prod)

```bash
gcloud run deploy celebration-event-planner --source . --port 8080 --allow-unauthenticated --set-env-vars LLM_PROVIDER=echo
# with Gemini:
gcloud run deploy celebration-event-planner --source . --set-env-vars LLM_PROVIDER=gemini,GEMINI_API_KEY=...,GEMINI_MODEL=gemini-2.0-flash
```

Why: Dockerfile honours $PORT, stateless-friendly (SQLite per instance — fine for demo/video).

## Option B: Render / Railway / Fly

- Build: `pip install -r requirements.txt`
- Start: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
- Env: `LLM_PROVIDER=echo` (or gemini/openai-compat keys). The app is a single-tenant demo with no
  authentication, so every visitor shares the same SQLite file — keep it that way for the demo
  video, and add auth before exposing it to real users.

## Option C: Vercel (Python)

- Keep `backend/app/main.py` as the entry point.
- This repo does NOT ship a Vercel routing config. If you deploy to Vercel, add one yourself routing / -> backend/app/main.py, or point the Vercel Python runtime at `backend/app/main.py` directly. The Dockerfile in this repo is for Render/Cloud Run, not Vercel.
- Note: serverless cold starts clear in-memory state — re-create events per session (call out in video).

## Configuration (every variable is read by `backend/app/config.py`)

| Variable | Default | Effect |
|---|---|---|
| `LLM_PROVIDER` | `echo` | `echo` (offline), `gemini`, `openai-compat` |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | empty / `gemini-2.0-flash` | Gemini credentials and model |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` | empty | OpenAI-compatible endpoint |
| `STORE_BACKEND` | `sqlite` | `sqlite` or `memory` (tests) |
| `DATABASE_URL` | `sqlite:///./data/events.db` | SQLite file path |
| `FRONTEND_ORIGIN` | `http://localhost:8000` | Comma-separated CORS allowlist; wildcards are dropped, never `*` |
| `RATE_LIMIT_PER_MIN` | `200` | Per-client sliding-window limit → 429 + `Retry-After` |
| `MAX_RATE_BUCKETS` | `10000` | Upper bound on tracked rate-limit buckets (LRU eviction) |
| `MAX_UPLOAD_BYTES` | `10485760` | Upload size cap (10 MB) |
| `MAX_STORE_EVENTS` | `5000` | Event-store capacity → 429 when full |
| `MAX_STORE_CHUNKS` | `1000` | Chunks retained per uploaded document |
| `MAX_DOCUMENTS` | `10` | Documents kept in the session document store → 429 + `Retry-After` when full |
| `PORT` | `8000` | Listen port |
| `LOG_LEVEL` | `info` | Root log level |

Copy `.env.example` to `.env` for local runs. `.env` is gitignored; only `.env.example` is tracked.

## Prod hardening (post-MVP)

- CORS is secure-by-default: the middleware is always installed, but the allowlist is parsed from
  `FRONTEND_ORIGIN` by `parse_allowed_origins`, which drops wildcards and malformed entries. An
  empty allowlist means no `Access-Control-Allow-Origin` header is sent and the browser blocks
  every cross-origin call. For cross-origin prod: `--set-env-vars FRONTEND_ORIGIN=https://your-app.run.app`.
- Security headers on (nosniff/DENY/no-referrer/CSP + HSTS + Permissions-Policy + no-store + X-Process-Time) + X-RateLimit-*/Retry-After + non-root Docker + HEALTHCHECK /health.
- Upload DoS-safe: extension + basename sanitization (traversal-safe) + size + %PDF- magic pre-parse, then a bounded pypdf parse (a PDF with no pages or no extractable text is rejected with 400); bounded store (MAX_STORE_EVENTS, 429 when full), bounded session document store (MAX_DOCUMENTS, 429 + Retry-After when full), bounded guest_count/top_k (422), sliding-window rate limit (RATE_LIMIT_PER_MIN=200, tested 429 + Retry-After), safe errors (no Traceback).
- Efficiency: bounded top_k fan-out, cached TF-IDF index (fitted once, query transform only), sanitized inputs, Pydantic bounds.
- Add Redis/pgvector for shared index across instances.
- Add auth + per-user event isolation (current MVP is demo, not multi-tenant prod).
- Add request logging (no PII) + tighter per-tier rate limits.

## Submission hygiene (evaluator parser)

- Single branch (main only), repo <10MB (code + fake data only; .ai/, .env, __pycache__/, .pytest_cache/, .coverage ignored via .gitignore).
- No secrets in git: keys via env only (.env.example has empty slots); verify with `pytest tests/test_code_quality.py -v`.
- Live URL must serve / (frontend) + /health (provider badge); keep LLM_PROVIDER=echo for deterministic demo/video.
