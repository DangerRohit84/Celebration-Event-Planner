# Video script — 2–3 min functionality walkthrough (required)

Record real app, no slides. Show URL bar at start (proves Live URL).

0:00–0:15 — Hook + disclaimer
- "Plan a wedding, birthday, or community event in minutes — budgets, timelines, vendors, and grounded ideas."
- Point to banner: "General planning information only - not professional advice. Verify with vendors and qualified planners."

0:15–0:45 — Create event
- Fill form: name "Priya & Arjun Wedding", type Wedding, date, guests 150, budget 500000.
- Show auto-generated budget breakdown, timeline milestones, vendor checklist.

0:45–1:20 — Personalized ideas (grounded)
- Ask "outdoor ceremony ideas" → show ideas + citations (source ids) + confidence badge (Grounded/Partial).
- Tick "Simple language" → re-ask → shorter, jargon-free wording, same citations, and the answer panel shows "Answered in simple language."

1:20–1:45 — Cannot Determine (trust moment — do not skip)
- Ask something NOT in corpus (e.g. "best honeymoon destination in Maldives").
- Show exact "Cannot Determine from the provided context." + Cannot Determine badge.

1:45–2:15 — Export
- Click "Export Plan" → show JSON with event + budget + timeline + vendors + disclaimer.

2:15–2:40 — Upload (security + real parsing)
- Upload a real PDF → show the response with `pages` and `chunks` (the file is really parsed).
- Upload a non-PDF → show the 400 error in the role=alert region (no blocking alert()).
- Upload an oversized file → 413.

2:40–3:00 — Close + stack
- "LLM-agnostic: offline echo by default, Gemini/OpenAI toggle. SQLite store, FastAPI, deploys anywhere incl. Cloud Run."
- End on Live URL + GitHub link.

## Sample ask queries (use these in the demo)

The demo event is the wedding created above, so the corpus is filtered to
wedding + all-event entries.

Grounded (expect citations + Grounded/Partial):
- "outdoor ceremony ideas"
- "budget-friendly decor ideas for a garden wedding"
- "photo booth props and instant prints"
- "digital invitations 6 weeks ahead with RSVP tracking"
- "day-of timeline shared with all vendors"

Cannot Determine (expect exact refusal + Cannot Determine badge):
- "best honeymoon destination in Maldives"
- "what is the capital of France"
- "stock market tips for 2026"

Note: the corpus is event-type filtered, so a corporate-only question asked
on the wedding event also refuses. That is the filter working, not a bug —
create a corporate event to see the corporate entries.

Plain-language toggle demo:
- Re-ask "outdoor ceremony ideas" with "Simple language" ticked → shorter, simpler wording, same citations.

Checklist: 1080p, captions on, no API keys visible, sample data is fake/redacted.
