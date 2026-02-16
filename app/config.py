"""Application configuration loaded from environment variables and .env file."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Global mode
    runbook_mode: str = Field(default="mock", description="Global mode: 'mock' or 'live'")

    # Mock settings
    mock_scenario: str = Field(default="high_cpu")
    mock_delay_enabled: bool = Field(default=True)

    # ML engine
    ml_engine_provider: str = Field(default="anthropic")
    anthropic_api_key: str = Field(default="")
    ml_model: str = Field(default="claude-sonnet-4-5-20250929")

    # ServiceNow
    servicenow_mode: str = Field(default="")
    servicenow_instance: str = Field(default="")
    servicenow_username: str = Field(default="")
    servicenow_password: str = Field(default="")

    # Datadog
    datadog_mode: str = Field(default="")
    datadog_api_key: str = Field(default="")
    datadog_app_key: str = Field(default="")

    # PagerDuty
    pagerduty_mode: str = Field(default="")
    pagerduty_api_key: str = Field(default="")

    # AWS
    aws_mode: str = Field(default="")
    aws_access_key_id: str = Field(default="")
    aws_secret_access_key: str = Field(default="")
    aws_region: str = Field(default="us-east-1")

    # Jira
    jira_mode: str = Field(default="")
    jira_url: str = Field(default="")
    jira_username: str = Field(default="")
    jira_api_token: str = Field(default="")

    # Slack
    slack_mode: str = Field(default="")
    slack_bot_token: str = Field(default="")

    def get_integration_mode(self, integration: str) -> str:
        """Return the effective mode for a given integration.

        Per-integration overrides take precedence over the global runbook_mode.
        """
        override = getattr(self, f"{integration}_mode", "")
        return override if override else self.runbook_mode

    @property
    def available_scenarios(self) -> list[str]:
        return [
            "high_cpu",
            "database_connection",
            "deployment_failure",
            "network_latency",
        ]


def get_settings() -> Settings:
    """Create and return the application settings singleton."""
    return Settings()
