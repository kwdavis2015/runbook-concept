"""Shared test fixtures for the Runbook Concept test suite."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.config import Settings
from core.models import (
    Action,
    ActionType,
    Alert,
    Classification,
    Finding,
    FindingType,
    Incident,
    IncidentStatus,
    ProblemCategory,
    RiskLevel,
    Severity,
    TimelineEntry,
)


@pytest.fixture
def mock_settings() -> Settings:
    """Return a Settings instance configured for mock mode."""
    return Settings(
        runbook_mode="mock",
        mock_scenario="high_cpu",
        mock_delay_enabled=False,
        ml_engine_provider="mock",
    )


@pytest.fixture
def sample_alert() -> Alert:
    return Alert(
        id="alert-001",
        name="High CPU Alert",
        host="prod-web-03",
        value=94.2,
        threshold=90.0,
        severity=Severity.HIGH,
        triggered_at=datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_classification() -> Classification:
    return Classification(
        category=ProblemCategory.COMPUTE,
        severity=Severity.HIGH,
        confidence=0.92,
        reasoning="CPU spike correlated with recent deployment.",
    )


@pytest.fixture
def sample_finding() -> Finding:
    return Finding(
        id="finding-001",
        finding_type=FindingType.ALERT,
        source="datadog",
        summary="High CPU alert on prod-web-03 (94.2%)",
        confidence=0.95,
        timestamp=datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_action() -> Action:
    return Action(
        id="action-001",
        action_type=ActionType.EXECUTE,
        description="Restart the java service on prod-web-03",
        risk_level=RiskLevel.MEDIUM,
        requires_approval=True,
        integration="compute",
        method="restart_service",
        params={"host": "prod-web-03", "service": "java"},
    )


@pytest.fixture
def sample_incident(sample_classification, sample_finding, sample_action) -> Incident:
    return Incident(
        id="INC-001",
        title="High CPU on prod-web-03",
        description="Production web server CPU at 94%",
        status=IncidentStatus.DIAGNOSING,
        severity=Severity.HIGH,
        category=ProblemCategory.COMPUTE,
        classification=sample_classification,
        findings=[sample_finding],
        actions=[sample_action],
        timeline=[
            TimelineEntry(
                timestamp=datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
                event_type="alert",
                summary="High CPU alert triggered on prod-web-03",
                source="datadog",
            ),
        ],
        created_at=datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    )
