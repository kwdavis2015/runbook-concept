"""Browse and manage the runbook library."""

from pathlib import Path

import streamlit as st


RUNBOOK_DIR = Path("runbooks")


def render() -> None:
    st.header("Runbook Library")

    if not RUNBOOK_DIR.exists():
        st.warning("Runbook directory not found.")
        return

    runbook_files = sorted(RUNBOOK_DIR.glob("*.yaml"))

    if not runbook_files:
        st.info(
            "No runbooks found. Add YAML runbook files to the `runbooks/` directory. "
            "Runbook content will be created in Phase 2."
        )
        return

    selected = st.selectbox(
        "Select a runbook",
        runbook_files,
        format_func=lambda p: p.stem.replace("_", " ").title(),
    )

    if selected:
        st.code(selected.read_text(), language="yaml")
