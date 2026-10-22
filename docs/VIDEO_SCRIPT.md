# Video script — 2–3 min functionality walkthrough (required)

Record real app, no slides. Show URL bar at start (proves Live URL).

0:00–0:15 — Hook + disclaimer
- "Plan a wedding, birthday, or community event in minutes — budgets, timelines, vendors, and grounded ideas."
- Point to banner: "General information only — not professional advice. Verify with vendors and qualified planners."

0:15–0:45 — Create event
- Fill form: name "Priya & Arjun Wedding", type Wedding, date, guests 150, budget 500000.
- Show auto-generated budget breakdown, timeline milestones, vendor checklist.

0:45–1:20 — Personalized ideas (grounded)
- Ask "outdoor ceremony ideas" → show ideas + citations (source ids) + confidence badge (Grounded/Partial).
- Toggle plain-language → re-ask → simpler wording, same citations.

1:20–1:45 — Cannot Determine (trust moment — do not skip)
- Ask something NOT in corpus (e.g. "best honeymoon destination in Maldives").
- Show exact "Cannot Determine from the provided context." + Cannot Determine badge.

1:45–2:15 — Export
- Click "Export Plan" → show JSON with event + budget + timeline + vendors + disclaimer.

2:15–2:40 — Upload guard (security)
- Upload a non-PDF → show 400 "PDF only" error in role=alert region (no blocking alert()).
- Upload oversized file → 413.

2:40–3:00 — Close + stack
- "LLM-agnostic: offline echo by default, Gemini/OpenAI toggle. SQLite store, FastAPI, deploys anywhere incl. Cloud Run."
- End on Live URL + GitHub link.

## Sample ask queries (use these in the demo)

Grounded (expect citations + Grounded/Partial):
- "outdoor ceremony ideas"
- "budget-friendly decor ideas for a garden wedding"
- "kids birthday party entertainment ideas"
- "community event permit and safety checklist"
- "corporate event catering and AV ideas"

Cannot Determine (expect exact refusal + Cannot Determine badge):
- "best honeymoon destination in Maldives"
- "what is the capital of France"
- "stock market tips for 2026"

Plain-language toggle demo:
- Re-ask "outdoor ceremony ideas" with plain language on → simpler wording, same citations.

Checklist: 1080p, captions on, no API keys visible, sample data is fake/redacted.
