"""Human approval UI for critical actions — implemented in Phase 5."""

from __future__ import annotations

import streamlit as st

from core.models import Action


def render_approval_gate(action: Action) -> bool | None:
    """Render an approval prompt for an action. Returns True/False/None (pending)."""
    st.warning(f"**Approval required** — {action.description} (risk: {action.risk_level})")
    col1, col2 = st.columns(2)
    if col1.button("Approve", key=f"approve_{action.id}"):
        return True
    if col2.button("Reject", key=f"reject_{action.id}"):
        return False
    return None
