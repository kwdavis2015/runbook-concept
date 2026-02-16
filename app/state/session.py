"""Streamlit session state management."""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.config import Settings, get_settings

# Keys used in st.session_state
_SETTINGS_KEY = "app_settings"
_INCIDENTS_KEY = "incidents"
_MESSAGES_KEY = "chat_messages"
_ACTIVE_INCIDENT_KEY = "active_incident_id"
_REGISTRY_KEY = "integration_registry"


def init_session_state() -> None:
    """Initialize all session state keys with defaults if not already set."""
    if _SETTINGS_KEY not in st.session_state:
        st.session_state[_SETTINGS_KEY] = get_settings()
    if _INCIDENTS_KEY not in st.session_state:
        st.session_state[_INCIDENTS_KEY] = []
    if _MESSAGES_KEY not in st.session_state:
        st.session_state[_MESSAGES_KEY] = []
    if _ACTIVE_INCIDENT_KEY not in st.session_state:
        st.session_state[_ACTIVE_INCIDENT_KEY] = None


def get_session_settings() -> Settings:
    """Return the current Settings from session state."""
    return st.session_state[_SETTINGS_KEY]


def set_session_settings(settings: Settings) -> None:
    """Replace the settings in session state."""
    st.session_state[_SETTINGS_KEY] = settings


def get_chat_messages() -> list[dict[str, Any]]:
    """Return the chat message history."""
    return st.session_state[_MESSAGES_KEY]


def add_chat_message(role: str, content: str) -> None:
    """Append a message to the chat history."""
    st.session_state[_MESSAGES_KEY].append({"role": role, "content": content})


def clear_chat_messages() -> None:
    """Clear the chat history."""
    st.session_state[_MESSAGES_KEY] = []


def get_incidents() -> list:
    """Return the list of tracked incidents."""
    return st.session_state[_INCIDENTS_KEY]


def set_active_incident(incident_id: str | None) -> None:
    """Set the currently focused incident."""
    st.session_state[_ACTIVE_INCIDENT_KEY] = incident_id


def get_active_incident_id() -> str | None:
    """Return the ID of the currently focused incident, if any."""
    return st.session_state[_ACTIVE_INCIDENT_KEY]
