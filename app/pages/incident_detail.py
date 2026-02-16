"""Single incident deep-dive view."""

import streamlit as st

from app.state.session import get_active_incident_id, get_incidents


def render() -> None:
    st.header("Incident Detail")

    active_id = get_active_incident_id()
    incidents = get_incidents()

    if not incidents:
        st.info("No incidents to display. Start a troubleshooting session from the **Chat** page.")
        return

    # Allow selection if no active incident
    incident_ids = [i.id for i in incidents]
    if active_id and active_id in incident_ids:
        idx = incident_ids.index(active_id)
    else:
        idx = 0

    selected_id = st.selectbox("Incident", incident_ids, index=idx)
    incident = next((i for i in incidents if i.id == selected_id), None)

    if not incident:
        st.error("Incident not found.")
        return

    # Header
    st.subheader(incident.title)
    col1, col2, col3 = st.columns(3)
    col1.metric("Status", incident.status)
    col2.metric("Severity", incident.severity)
    col3.metric("Category", incident.category)

    # Timeline (placeholder — component built in Phase 5)
    st.divider()
    st.subheader("Timeline")
    if incident.timeline:
        for entry in incident.timeline:
            st.write(f"**{entry.timestamp}** — {entry.summary}")
    else:
        st.caption("No timeline entries yet.")

    # Findings
    st.divider()
    st.subheader("Findings")
    if incident.findings:
        for finding in incident.findings:
            st.write(f"- [{finding.finding_type}] {finding.summary}")
    else:
        st.caption("No findings yet.")

    # Actions
    st.divider()
    st.subheader("Actions")
    if incident.actions:
        for action in incident.actions:
            status = "Executed" if action.executed_at else ("Approved" if action.approved else "Pending")
            st.write(f"- **{action.description}** — {status} (risk: {action.risk_level})")
    else:
        st.caption("No actions yet.")
