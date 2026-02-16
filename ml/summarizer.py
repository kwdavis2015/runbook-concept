"""Incident summarization.

The summarizer is simple — it sends the incident data through the
summarization prompt and returns the LLM's prose response directly.
Parsing logic lives here for consistency, though for summarization
the raw text is typically used as-is.
"""

from __future__ import annotations


def clean_summary(raw: str) -> str:
    """Clean up a raw LLM summary response."""
    text = raw.strip()
    # Remove markdown heading if the LLM prepends one
    lines = text.split("\n")
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    return "\n".join(lines).strip()
