"""Tests for application configuration."""

from app.config import Settings


class TestSettingsDefaults:
    def test_default_mode_is_mock(self):
        s = Settings(runbook_mode="mock")
        assert s.runbook_mode == "mock"

    def test_default_scenario(self):
        s = Settings()
        assert s.mock_scenario == "high_cpu"

    def test_default_delay_enabled(self):
        s = Settings()
        assert s.mock_delay_enabled is True

    def test_available_scenarios(self):
        s = Settings()
        scenarios = s.available_scenarios
        assert "high_cpu" in scenarios
        assert "database_connection" in scenarios
        assert "deployment_failure" in scenarios
        assert "network_latency" in scenarios
        assert len(scenarios) == 4


class TestIntegrationModeOverride:
    def test_global_mode_used_when_no_override(self):
        s = Settings(runbook_mode="mock", servicenow_mode="")
        assert s.get_integration_mode("servicenow") == "mock"

    def test_per_integration_override(self):
        s = Settings(runbook_mode="mock", servicenow_mode="live")
        assert s.get_integration_mode("servicenow") == "live"

    def test_global_live_mode(self):
        s = Settings(runbook_mode="live", datadog_mode="")
        assert s.get_integration_mode("datadog") == "live"

    def test_unknown_integration_falls_back_to_global(self):
        s = Settings(runbook_mode="mock")
        assert s.get_integration_mode("nonexistent") == "mock"

    def test_multiple_overrides(self):
        s = Settings(
            runbook_mode="mock",
            servicenow_mode="live",
            datadog_mode="live",
            pagerduty_mode="",
        )
        assert s.get_integration_mode("servicenow") == "live"
        assert s.get_integration_mode("datadog") == "live"
        assert s.get_integration_mode("pagerduty") == "mock"
