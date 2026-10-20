# Celebration & Event Planner - GenAI Planning Assistant (MVP scaffold)

GenAI-powered planning assistant for weddings, birthdays, and community events:
budgets, timelines, vendor checklists, and personalized ideas.

## Status
Scaffold only. Implementation pending confirmation of name/scope.

## Quickstart (planned)
```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.app.main:app --reload --port 8000
```

## Layout
See `backend/app/` for modules. Tests in `tests/`.

## Design notes (100/100 targets)
- Persistent store (SQLite) by default via repository pattern (pluggable).
- Pinned dependencies (no optional drops).
- Bounded reads + streaming for any file input.
- Structured parser with fallback (not regex-only).
- Accessibility + security + efficiency baked in.
