"""Streamlit entrypoint for the Runbook Concept application."""

import streamlit as st

from app.pages.chat import render as chat_page
from app.pages.dashboard import render as dashboard_page
from app.pages.incident_detail import render as incident_detail_page
from app.pages.runbooks import render as runbooks_page
from app.pages.settings import render as settings_page
from app.state.session import get_session_settings, init_session_state

# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

init_session_state()

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

pages = st.navigation(
    [
        st.Page(chat_page, title="Chat", icon="💬", url_path="chat", default=True),
        st.Page(dashboard_page, title="Dashboard", icon="📊", url_path="dashboard"),
        st.Page(runbooks_page, title="Runbook Library", icon="📚", url_path="runbooks"),
        st.Page(incident_detail_page, title="Incident Detail", icon="🔍", url_path="incident"),
        st.Page(settings_page, title="Settings", icon="⚙️", url_path="settings"),
    ]
)

# ---------------------------------------------------------------------------
# Sidebar branding (below the built-in page nav)
# ---------------------------------------------------------------------------

settings = get_session_settings()

with st.sidebar:
    st.title("📒 Runbook Concept")
    st.caption(f"Mode: **{settings.runbook_mode}** | Scenario: **{settings.mock_scenario}**")

# ---------------------------------------------------------------------------
# Run the selected page
# ---------------------------------------------------------------------------

pages.run()
