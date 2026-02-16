"""Visual timeline component for diagnostic steps — implemented in Phase 5."""

from __future__ import annotations

import streamlit as st

from core.models import TimelineEntry


def render_timeline(entries: list[TimelineEntry]) -> None:
    """Render an incident timeline. Placeholder for Phase 5 implementation."""
    if not entries:
        st.caption("No timeline entries.")
        return

    for entry in entries:
        st.write(f"**{entry.timestamp:%H:%M:%S}** — {entry.summary}")
