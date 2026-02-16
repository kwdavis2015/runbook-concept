"""Tests for the integration registry and provider factory."""

import pytest

from app.config import Settings
from core.exceptions import ProviderNotFoundError
from integrations.mock.mock_aws import MockAWS
from integrations.mock.mock_datadog import MockDatadog
from integrations.mock.mock_pagerduty import MockPagerDuty
from integrations.mock.mock_servicenow import MockServiceNow
from integrations.mock.mock_slack import MockSlack
from integrations.registry import IntegrationRegistry


@pytest.fixture
def mock_settings():
    return Settings(runbook_mode="mock", mock_delay_enabled=False)


@pytest.fixture
def registry(mock_settings):
    return IntegrationRegistry(mock_settings)


class TestMockResolution:
    def test_ticketing_resolves_to_mock_servicenow(self, registry):
        provider = registry.get_provider("ticketing")
        assert isinstance(provider, MockServiceNow)

    def test_monitoring_resolves_to_mock_datadog(self, registry):
        provider = registry.get_provider("monitoring")
        assert isinstance(provider, MockDatadog)

    def test_alerting_resolves_to_mock_pagerduty(self, registry):
        provider = registry.get_provider("alerting")
        assert isinstance(provider, MockPagerDuty)

    def test_compute_resolves_to_mock_aws(self, registry):
        provider = registry.get_provider("compute")
        assert isinstance(provider, MockAWS)

    def test_communication_resolves_to_mock_slack(self, registry):
        provider = registry.get_provider("communication")
        assert isinstance(provider, MockSlack)


class TestProviderCaching:
    def test_same_instance_returned(self, registry):
        first = registry.get_provider("ticketing")
        second = registry.get_provider("ticketing")
        assert first is second

    def test_reset_clears_cache(self, registry):
        first = registry.get_provider("ticketing")
        registry.reset()
        second = registry.get_provider("ticketing")
        assert first is not second


class TestErrorHandling:
    def test_invalid_category_raises(self, registry):
        with pytest.raises(ProviderNotFoundError) as exc_info:
            registry.get_provider("nonexistent")
        assert "nonexistent" in str(exc_info.value)

    def test_error_includes_category(self, registry):
        with pytest.raises(ProviderNotFoundError) as exc_info:
            registry.get_provider("invalid_category")
        assert exc_info.value.category == "invalid_category"
