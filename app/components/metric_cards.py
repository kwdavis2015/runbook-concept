"""Dashboard metric card widgets — implemented in Phase 5."""

from __future__ import annotations

import streamlit as st


def render_metric_card(label: str, value: str | int | float, delta: str | None = None) -> None:
    """Render a single metric card."""
    st.metric(label=label, value=value, delta=delta)
