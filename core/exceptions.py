"""Custom exceptions for the Runbook Concept application."""


class RunbookError(Exception):
    """Base exception for all runbook errors."""


class ConfigurationError(RunbookError):
    """Raised when configuration is invalid or missing."""


class IntegrationError(RunbookError):
    """Raised when an integration call fails."""

    def __init__(self, provider: str, message: str):
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class ProviderNotFoundError(RunbookError):
    """Raised when a requested integration provider is not registered."""

    def __init__(self, category: str, provider: str | None = None):
        self.category = category
        self.provider = provider
        detail = f" (provider={provider})" if provider else ""
        super().__init__(f"No provider found for category '{category}'{detail}")


class ApprovalRequiredError(RunbookError):
    """Raised when an action requires human approval before execution."""

    def __init__(self, action_id: str, risk_level: str):
        self.action_id = action_id
        self.risk_level = risk_level
        super().__init__(f"Action '{action_id}' requires approval (risk={risk_level})")


class RunbookParseError(RunbookError):
    """Raised when a runbook YAML file cannot be parsed."""

    def __init__(self, path: str, reason: str):
        self.path = path
        super().__init__(f"Failed to parse runbook '{path}': {reason}")


class MLEngineError(RunbookError):
    """Raised when the ML engine encounters an error."""
