"""Settings page — toggle mock/live mode, select scenario, view integration status."""

import streamlit as st

from app.config import Settings
from app.state.session import get_session_settings, set_session_settings


def render() -> None:
    st.header("Settings")

    settings = get_session_settings()

    # ------------------------------------------------------------------
    # Global mode
    # ------------------------------------------------------------------
    st.subheader("Global Mode")
    mode = st.radio(
        "Runbook mode",
        options=["mock", "live"],
        index=0 if settings.runbook_mode == "mock" else 1,
        horizontal=True,
        help="In mock mode, all integrations use simulated data. Switch to live to use real APIs.",
    )

    # ------------------------------------------------------------------
    # Mock scenario selector
    # ------------------------------------------------------------------
    st.subheader("Mock Scenario")
    scenarios = settings.available_scenarios
    scenario = st.selectbox(
        "Active scenario",
        options=scenarios,
        index=scenarios.index(settings.mock_scenario) if settings.mock_scenario in scenarios else 0,
        help="Select which pre-built incident scenario the mock services simulate.",
        disabled=(mode != "mock"),
    )

    mock_delay = st.checkbox(
        "Simulate API latency",
        value=settings.mock_delay_enabled,
        disabled=(mode != "mock"),
    )

    # ------------------------------------------------------------------
    # ML engine
    # ------------------------------------------------------------------
    st.subheader("ML Engine")
    ml_provider = st.selectbox(
        "ML provider",
        options=["mock", "anthropic"],
        index=0 if settings.ml_engine_provider == "mock" else 1,
    )

    ml_model = st.text_input("Model", value=settings.ml_model, disabled=(ml_provider == "mock"))

    # ------------------------------------------------------------------
    # Integration overrides
    # ------------------------------------------------------------------
    st.subheader("Integration Status")

    integrations = [
        ("ServiceNow", "servicenow"),
        ("Datadog", "datadog"),
        ("PagerDuty", "pagerduty"),
        ("AWS", "aws"),
        ("Jira", "jira"),
        ("Slack", "slack"),
    ]

    for display_name, key in integrations:
        effective = settings.get_integration_mode(key)
        label = "mock" if effective == "mock" else "live"
        icon = "🟡" if label == "mock" else "🟢"
        st.write(f"{icon} **{display_name}** — {label}")

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------
    st.divider()
    if st.button("Apply settings", type="primary"):
        updated = Settings(
            runbook_mode=mode,
            mock_scenario=scenario,
            mock_delay_enabled=mock_delay,
            ml_engine_provider=ml_provider,
            ml_model=ml_model,
            # Carry forward credential fields from current settings
            anthropic_api_key=settings.anthropic_api_key,
            servicenow_mode=settings.servicenow_mode,
            servicenow_instance=settings.servicenow_instance,
            servicenow_username=settings.servicenow_username,
            servicenow_password=settings.servicenow_password,
            datadog_mode=settings.datadog_mode,
            datadog_api_key=settings.datadog_api_key,
            datadog_app_key=settings.datadog_app_key,
            pagerduty_mode=settings.pagerduty_mode,
            pagerduty_api_key=settings.pagerduty_api_key,
            aws_mode=settings.aws_mode,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            aws_region=settings.aws_region,
            jira_mode=settings.jira_mode,
            jira_url=settings.jira_url,
            jira_username=settings.jira_username,
            jira_api_token=settings.jira_api_token,
            slack_mode=settings.slack_mode,
            slack_bot_token=settings.slack_bot_token,
        )
        set_session_settings(updated)
        st.success("Settings applied.")
        st.rerun()
