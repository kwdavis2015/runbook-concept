"""Integration registry and factory for resolving providers based on configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.exceptions import ProviderNotFoundError

if TYPE_CHECKING:
    from app.config import Settings
    from integrations.base import (
        AlertingProvider,
        CommunicationProvider,
        MonitoringProvider,
        TicketingProvider,
    )

# Maps category → mode → import path (module, class_name).
# Providers are imported lazily to avoid loading unused dependencies.
PROVIDER_MAP: dict[str, dict[str, tuple[str, str]]] = {
    "ticketing": {
        "mock": ("integrations.mock.mock_servicenow", "MockServiceNow"),
        "servicenow": ("integrations.providers.servicenow.client", "ServiceNowClient"),
        "jira": ("integrations.providers.jira.client", "JiraClient"),
    },
    "monitoring": {
        "mock": ("integrations.mock.mock_datadog", "MockDatadog"),
        "datadog": ("integrations.providers.datadog.client", "DatadogClient"),
    },
    "alerting": {
        "mock": ("integrations.mock.mock_pagerduty", "MockPagerDuty"),
        "pagerduty": ("integrations.providers.pagerduty.client", "PagerDutyClient"),
    },
    "compute": {
        "mock": ("integrations.mock.mock_aws", "MockAWS"),
        "aws": ("integrations.providers.aws.client", "AWSClient"),
    },
    "communication": {
        "mock": ("integrations.mock.mock_slack", "MockSlack"),
        "slack": ("integrations.providers.slack.client", "SlackClient"),
    },
}

# Maps integration mode keywords to categories for per-integration override lookup.
_MODE_TO_CATEGORY: dict[str, str] = {
    "servicenow": "ticketing",
    "jira": "ticketing",
    "datadog": "monitoring",
    "pagerduty": "alerting",
    "aws": "compute",
    "slack": "communication",
}


def _import_class(module_path: str, class_name: str) -> type:
    """Lazily import a provider class by its module path and class name."""
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class IntegrationRegistry:
    """Resolves and caches integration providers based on application configuration."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[str, object] = {}

    def _resolve_mode(self, category: str) -> str:
        """Determine the effective mode for a category.

        Checks for per-integration overrides (e.g. SERVICENOW_MODE=live) before
        falling back to the global RUNBOOK_MODE.
        """
        for integration_key, cat in _MODE_TO_CATEGORY.items():
            if cat == category:
                override = self._settings.get_integration_mode(integration_key)
                if override and override != "mock":
                    return integration_key
        return "mock"

    def get_provider(
        self, category: str
    ) -> TicketingProvider | MonitoringProvider | AlertingProvider | CommunicationProvider:
        """Return the provider instance for the given category.

        Providers are instantiated once and cached for the lifetime of the registry.
        """
        if category in self._cache:
            return self._cache[category]  # type: ignore[return-value]

        if category not in PROVIDER_MAP:
            raise ProviderNotFoundError(category)

        mode = self._resolve_mode(category)
        providers = PROVIDER_MAP[category]

        if mode not in providers:
            raise ProviderNotFoundError(category, mode)

        module_path, class_name = providers[mode]
        cls = _import_class(module_path, class_name)
        instance = cls(self._settings)
        self._cache[category] = instance
        return instance  # type: ignore[return-value]

    def reset(self) -> None:
        """Clear the provider cache, forcing re-resolution on next access."""
        self._cache.clear()
