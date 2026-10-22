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
- Env: `LLM_PROVIDER=echo` (or gemini/openai-compat keys) + `DEMO_MODE=true` on dashboard (keeps single-tenant demo global fallback for video stability; prod multi-user sets `DEMO_MODE=false`).

## Option C: Vercel (Python)

- Keep `backend/app/main.py` as the entry; add `vercel.json` routing `/ -> backend/app/main.py` if needed.
- Note: serverless cold starts clear in-memory state — re-create events per session (call out in video).

## Prod hardening (post-MVP)

- CORS is secure-by-default (no middleware unless FRONTEND_ORIGIN/ALLOWED_ORIGINS set — never *). For cross-origin prod: `--set-env-vars FRONTEND_ORIGIN=https://your-app.run.app`.
- Security headers on (nosniff/DENY/no-referrer/CSP + HSTS + Permissions-Policy + no-store + X-Process-Time) + X-RateLimit-*/Retry-After + non-root Docker + HEALTHCHECK /health.
- Upload DoS-safe: extension + basename sanitization (traversal-safe) + size + %PDF- magic pre-parse, bounded store (MAX_STORE_EVENTS, 429 when full), bounded guest_count/top_k (422), sliding-window rate limit (RATE_LIMIT_PER_MIN=200, tested 429 + Retry-After), safe errors (no Traceback).
- Efficiency: bounded top_k/doc_ids fan-out, sanitized inputs, Pydantic bounds.
- Add Redis/pgvector for shared index across instances.
- Add auth + per-user event isolation (current MVP is demo, not multi-tenant prod).
- Add request logging (no PII) + tighter per-tier rate limits.

## Submission hygiene (evaluator parser)

- Single branch (main only), repo <10MB (code + fake data only; .ai/, .env, __pycache__/, .pytest_cache/, .coverage ignored via .gitignore).
- No secrets in git: keys via env only (.env.example has empty slots); verify with `pytest tests/test_code_quality.py -v`.
- Live URL must serve / (frontend) + /health (provider badge); keep LLM_PROVIDER=echo for deterministic demo/video.
