"""Shared prompt constants: the exact strings every surface must match.

These are the trust-critical texts of the app: the disclaimer quoted on
every surface, the exact refusal string, the plain-language rule, the two
rendering headers, and the three numbered rules of the grounded prompt.
They live in a leaf module so prompt builders, renderers, and confidence
calibration can share them without circular imports.
"""

from __future__ import annotations

DISCLAIMER = (
    "General planning information only - not professional advice. "
    "Verify with vendors and qualified planners."
)

CANNOT_DETERMINE = "Cannot Determine from the provided context."

PLAIN_LANGUAGE_RULE = (
    "Answer in short, plain, jargon-free sentences. Use everyday words, "
    "one idea per sentence, and avoid technical or legal terminology."
)

# Header of the standard rendering and of the plain-language rendering.
# The plain header is one character longer than the standard one, but
# dropping the bracketed source markers saves five characters per bullet,
# so the plain rendering is always the shorter of the two.
STANDARD_HEADER = "Ideas:"
PLAIN_HEADER = "Simple:"

# The three numbered rules of the grounded prompt.
GROUNDING_RULE = (
    "Rule 1: Use ONLY the provided context. Cite source ids in brackets."
)
REFUSAL_RULE = (
    "Rule 2: If context is insufficient, reply exactly: "
    "Cannot Determine from the provided context."
)
DISCLAIMER_RULE = (
    "Rule 3: Say that this is general planning information and not "
    f"professional advice, and end your answer with: {DISCLAIMER}"
)
