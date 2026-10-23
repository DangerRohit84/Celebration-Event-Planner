"""Planning templates: budget splits, vendor categories, milestone offsets.

Pure data, no logic. The planning engine
(:mod:`backend.app.planner`) reads these tables to generate a budget
breakdown, a timeline, and a vendor checklist for an event.
"""

from __future__ import annotations

# Default budget allocation percentages by event type.
BUDGET_TEMPLATES: dict[str, list[tuple[str, float]]] = {
    "wedding": [
        ("venue", 0.30),
        ("catering", 0.25),
        ("decor", 0.12),
        ("photography", 0.10),
        ("attire", 0.08),
        ("music", 0.06),
        ("invitations", 0.03),
        ("transport", 0.03),
        ("contingency", 0.03),
    ],
    "birthday": [
        ("venue", 0.20),
        ("catering", 0.30),
        ("decor", 0.15),
        ("cake", 0.10),
        ("entertainment", 0.12),
        ("invitations", 0.05),
        ("gifts", 0.05),
        ("contingency", 0.03),
    ],
    "community": [
        ("venue", 0.25),
        ("catering", 0.20),
        ("decor", 0.10),
        ("sound_av", 0.12),
        ("permits", 0.08),
        ("marketing", 0.08),
        ("volunteers", 0.05),
        ("contingency", 0.12),
    ],
    "corporate": [
        ("venue", 0.25),
        ("catering", 0.20),
        ("av", 0.15),
        ("decor", 0.08),
        ("speakers", 0.12),
        ("marketing", 0.08),
        ("swag", 0.07),
        ("contingency", 0.05),
    ],
    "other": [
        ("venue", 0.30),
        ("catering", 0.25),
        ("decor", 0.15),
        ("misc", 0.20),
        ("contingency", 0.10),
    ],
}

VENDOR_CATEGORIES: dict[str, list[str]] = {
    "wedding": [
        "venue",
        "caterer",
        "decorator",
        "photographer",
        "videographer",
        "dj_band",
        "florist",
        "makeup",
        "transport",
        "cake",
    ],
    "birthday": [
        "venue",
        "caterer",
        "decorator",
        "entertainer",
        "cake",
        "photographer",
    ],
    "community": ["venue", "caterer", "sound_av", "permits", "marketing", "volunteers"],
    "corporate": [
        "venue",
        "caterer",
        "av",
        "decorator",
        "speakers",
        "marketing",
        "swag",
    ],
    "other": ["venue", "caterer", "decorator"],
}

# Milestone offsets (days before event) -> title
MILESTONE_OFFSETS: list[tuple[int, str]] = [
    (180, "Set budget and guest list"),
    (120, "Book venue"),
    (90, "Book caterer and key vendors"),
    (60, "Send invitations"),
    (30, "Finalize menu and decor"),
    (14, "Confirm RSVPs and headcount"),
    (7, "Final vendor confirmations"),
    (1, "Day-before checklist"),
    (0, "Event day"),
]
