"""Side panel showing gathered evidence — implemented in Phase 5."""

from __future__ import annotations

import streamlit as st

from core.models import Finding


def render_context_panel(findings: list[Finding]) -> None:
    """Render a panel of gathered findings."""
    st.subheader("Evidence")
    if not findings:
        st.caption("No evidence gathered yet.")
        return

    for finding in findings:
        with st.expander(f"[{finding.finding_type}] {finding.source}"):
            st.write(finding.summary)
            if finding.details:
                st.json(finding.details)
