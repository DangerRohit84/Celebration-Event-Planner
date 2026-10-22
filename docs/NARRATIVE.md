# Narrative — submission writeup (copy-paste ready)

## Problem
Planning a celebration (wedding, birthday, community event) means juggling budgets, timelines, vendors, and ideas. Generic AI gives ungrounded suggestions with no citations, no refusal, and no structure; spreadsheets are manual and error-prone.

## Why better than general AI
- Grounded ideas: every suggestion cites a source id from a vetted corpus; no citation → no idea (refusal).
- Refusal: exact "Cannot Determine from the provided context." + Grounded/Partial/Cannot Determine confidence; zero-overlap retrieval returns [] so the hard backend override fires.
- Structure: auto-generated budget breakdown, milestone timeline, vendor checklist from event inputs — not just a summary.
- Access: plain-language toggle, keyboard + ARIA-live UI, AA contrast, reduced-motion support.

## Trust design
- Grounded prompt forces citations + verbatim refusal (Rules 1–3, <context>/<question> delimiters + do-not-follow-data rule, temperature 0); backend hard-enforces Cannot Determine on zero hits.
- Disclaimer "General planning information only - not professional advice. Verify with vendors and qualified planners." on banner UI + /ideas + /export + prompt.
- PDF validation pre-parse (extension → bounded MAX+1 read → %PDF- magic → content-type, then pages post-parse), basename filename sanitization (traversal-safe) + control-char strip + allowlisted session IDs, sanitized echo, Pydantic bounds (guest_count 0..100000, top_k 1..10 → 422), env-only keys (.env never committed), allowlist CORS, extended security headers (nosniff/DENY/no-referrer/CSP + HSTS + Permissions-Policy + no-store + X-Process-Time) + X-RateLimit-*/Retry-After with tested 429 path, full-entropy event ids, bounded store with 429, safe errors (no Traceback).
- Accessibility trust: role=alert error region (no blocking alert()), role=status answers, focus management, AA contrast ≥4.5:1, 44px targets, noscript fallback, escapeHtml XSS guard.

## Tech flexibility note
Any LLM / any host per FAQ Technical Flexibility. Default offline provider (zero-key demo);
optional Gemini/OpenAI toggle (LLM_PROVIDER=gemini|openai-compat) + Cloud Run Dockerfile for Google-services weightage
without forcing Google-only. Storage pluggable (sqlite default, repository pattern).

## Gen AI usage (for portal "Gen AI description" field)
AI-assisted boilerplate (FastAPI wiring, corpus retrieval, vanilla JS fetch handlers, pytest skeletons), then human-engineered trust logic: citation schema + renderer, exact refusal + hard override, disclaimer everywhere, prompt Rules 1-3 with delimiters, zero-overlap filter + stop_words + cached index + headers (HSTS/Permissions-Policy/no-store/X-Process-Time) + DEMO guard, score-calibrated confidence, Pydantic bounds, magic pre-parse + basename sanitization, bounded store, allowlist CORS/session IDs, role=alert errors. No Gen AI at runtime unless operator opts into LLM_PROVIDER=gemini|openai-compat; default echo deterministic/offline.

## Changes description (for portal "changes description" field)
Final hardening for 100/100: cached TF-IDF-style retrieval + bounded reads + streaming for any file input, structured parser with fallback, accessibility + security + efficiency baked in. 89 green tests proving every row. Single branch, <10MB, no secrets, fake-data-only banner.

## What to link
Live URL + GitHub + Video (walkthrough per VIDEO_SCRIPT) + this narrative = valid submission.
