"""Active incidents and metrics dashboard."""

import streamlit as st

from app.state.session import get_incidents


def render() -> None:
    st.header("Incident Dashboard")

    incidents = get_incidents()

    # Metric summary cards
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Active Incidents", len(incidents))
    col2.metric("Critical", sum(1 for i in incidents if getattr(i, "severity", "") == "critical"))
    col3.metric("Awaiting Approval", sum(1 for i in incidents if getattr(i, "status", "") == "awaiting_approval"))
    col4.metric("Resolved Today", 0)

    st.divider()

    if not incidents:
        st.info(
            "No active incidents. Use the **Chat** page to report a problem, "
            "or the mock scenarios will populate data once the orchestrator is connected."
        )
    else:
        for incident in incidents:
            with st.expander(f"{incident.id} — {incident.title}"):
                st.write(f"**Status:** {incident.status}")
                st.write(f"**Severity:** {incident.severity}")
                st.write(f"**Category:** {incident.category}")
