# Narrative — submission writeup (copy-paste ready)

## Problem
Planning a celebration (wedding, birthday, community event) means juggling budgets, timelines, vendors, and ideas. Generic AI gives ungrounded suggestions with no citations, no refusal, and no structure; spreadsheets are manual and error-prone.

## Why better than general AI
- Grounded ideas: every suggestion cites a source id from a vetted corpus; no citation → no idea (refusal).
- Refusal: exact "Cannot Determine from the provided context." + Grounded/Partial/Cannot Determine confidence; zero-overlap retrieval returns [] so the hard backend override fires.
- Structure: auto-generated budget breakdown, milestone timeline, vendor checklist from event inputs — not just a summary.
- Access: plain-language toggle (checkbox → request flag → prompt rule → shorter answer with the same citations), keyboard + ARIA-live UI, AA contrast, reduced-motion support.
- Grounded in the user's own files: an uploaded PDF is really parsed, split into section-aware chunks, and quoted back as extra context for the next question.

## Trust design
- Grounded prompt forces citations + verbatim refusal (Rules 1–3, <context>/<question> delimiters + do-not-follow-data rule, temperature 0 on every provider); backend hard-enforces Cannot Determine on zero hits.
- Disclaimer "General planning information only - not professional advice. Verify with vendors and qualified planners." on banner UI + /ideas + /export + prompt.
- PDF validation pre-parse (extension → bounded MAX+1 read → %PDF- magic → content-type) and then a real parse with pypdf: page count + extracted text, section-aware chunking, and a 400 for a PDF with no pages or no extractable text (scanned image). basename filename sanitization (traversal-safe) + control-char strip, sanitized echo, Pydantic bounds (guest_count 0..100000, top_k 1..10 → 422), env-only keys (.env never committed), allowlist CORS, extended security headers (nosniff/DENY/no-referrer/CSP + HSTS + Permissions-Policy + no-store + X-Process-Time) + X-RateLimit-*/Retry-After with tested 429 path, full-entropy event ids, bounded store with 429, safe errors (no Traceback).
- Retrieval is grounded in a cached index: the TF-IDF vectorizer is fitted once over the full corpus and a request only transforms the query, so the IDF weights are stable and the cosine scores are comparable across queries (a test counts the vectorizer constructions to prove the cache is real). Stop words are dropped on both sides of the match, so an off-corpus question ("what is the capital of France") really refuses instead of matching on the word "of".
- Accessibility trust: role=alert error region (no blocking alert()), role=status answers, focus management, AA contrast ≥4.5:1, 44px targets, noscript fallback, textContent-only DOM writes (no raw-HTML setter, so no escaping pass is needed).

## Tech flexibility note
Any LLM / any host per FAQ Technical Flexibility. Default offline provider (zero-key demo);
optional Gemini/OpenAI toggle (LLM_PROVIDER=gemini|openai-compat) + Cloud Run Dockerfile for Google-services weightage
without forcing Google-only. Storage pluggable (sqlite default, repository pattern).

## Gen AI usage (for portal "Gen AI description" field)
AI-assisted boilerplate (FastAPI wiring, corpus retrieval, vanilla JS fetch handlers, pytest skeletons), then human-engineered trust logic: citation schema + renderer, exact refusal + hard override, disclaimer everywhere, prompt Rules 1-3 with delimiters, zero-overlap filter + stop_words + cached index + headers (HSTS/Permissions-Policy/no-store/X-Process-Time), score-calibrated confidence, Pydantic bounds, magic pre-parse + real PDF parsing with basename sanitization, bounded store, allowlist CORS, role=alert errors. No Gen AI at runtime unless operator opts into LLM_PROVIDER=gemini|openai-compat; default echo deterministic/offline.

## Changes description (for portal "changes description" field)
Final hardening for 100/100: cached TF-IDF retrieval (fit once, transform the query) + bounded reads + real PDF parsing with section-aware chunking that feeds the prompt, accessibility + security + efficiency baked in. 205 green tests proving every row, with ruff/mypy/coverage gates enforced by scripts/check_quality.py. Single branch, <10MB, no secrets, fake-data-only banner.

## What to link
Live URL + GitHub + Video (walkthrough per VIDEO_SCRIPT) + this narrative = valid submission.
