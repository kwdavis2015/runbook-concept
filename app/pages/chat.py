"""Conversational troubleshooting interface."""

import streamlit as st

from app.state.session import add_chat_message, clear_chat_messages, get_chat_messages


def render() -> None:
    st.header("Chat — Troubleshooting Assistant")

    messages = get_chat_messages()

    # Display chat history
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Describe the problem you're seeing..."):
        add_chat_message("user", prompt)
        with st.chat_message("user"):
            st.markdown(prompt)

        # Placeholder — will be replaced by orchestrator in Phase 4
        response = (
            f"Received your report: *{prompt}*\n\n"
            "The orchestrator is not yet connected. "
            "This will be wired up in Phase 4."
        )
        add_chat_message("assistant", response)
        with st.chat_message("assistant"):
            st.markdown(response)

    # Sidebar controls
    with st.sidebar:
        if st.button("Clear chat"):
            clear_chat_messages()
            st.rerun()
