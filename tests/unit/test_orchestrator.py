"""Unit tests for core/orchestrator.py — Orchestrator."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.config import Settings
from core.approval import ApprovalPolicy, ApprovalPolicyType
from core.models import (
    Action,
    ActionType,
    Alert,
    Classification,
    DiagnosticResult,
    Finding,
    FindingType,
    Incident,
    IncidentStatus,
    ProblemCategory,
    RecommendationSet,
    ActionRecommendation,
    RiskLevel,
    Severity,
    VerificationResult,
)
from core.orchestrator import Orchestrator
from integrations.registry import IntegrationRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings() -> Settings:
    return Settings(
        runbook_mode="mock",
        mock_scenario="high_cpu",
        mock_delay_enabled=False,
        ml_engine_provider="mock",
    )


@pytest.fixture
def mock_registry():
    registry = MagicMock(spec=IntegrationRegistry)
    return registry


@pytest.fixture
def mock_ml():
    ml = MagicMock()
    ml.classify = AsyncMock(return_value=Classification(
        category=ProblemCategory.COMPUTE,
        severity=Severity.HIGH,
        confidence=0.9,
        reasoning="CPU spike",
    ))
    ml.diagnose = AsyncMock(return_value=DiagnosticResult(
        root_cause="Memory leak in java process",
        evidence_summary="CPU at 94% sustained",
        confidence=0.85,
        contributing_factors=["Recent deployment"],
        affected_components=["prod-web-03"],
    ))
    ml.recommend = AsyncMock(return_value=RecommendationSet(
        recommendations=[
            ActionRecommendation(
                description="Restart java service",
                risk_level=RiskLevel.MEDIUM,
                requires_approval=True,
                integration="compute",
                method="restart_service",
                params={"host": "prod-web-03", "service": "java"},
            ),
            ActionRecommendation(
                description="Notify on-call",
                risk_level=RiskLevel.LOW,
                requires_approval=False,
                integration="communication",
                method="send_message",
                params={"channel": "ops", "message": "High CPU alert"},
            ),
        ],
        summary="Restart service and notify on-call",
    ))
    ml.summarize = AsyncMock(return_value="Incident resolved after restarting java service.")
    return ml


@pytest.fixture
def orchestrator(settings, mock_registry, mock_ml) -> Orchestrator:
    return Orchestrator(settings=settings, registry=mock_registry, ml_engine=mock_ml)


@pytest.fixture
def sample_action_low() -> Action:
    return Action(
        id="act-low",
        action_type=ActionType.NOTIFY,
        description="Notify on-call",
        risk_level=RiskLevel.LOW,
        requires_approval=False,
    )


@pytest.fixture
def sample_action_medium() -> Action:
    return Action(
        id="act-med",
        action_type=ActionType.EXECUTE,
        description="Restart service",
        risk_level=RiskLevel.MEDIUM,
        requires_approval=True,
        integration="compute",
        method="restart_service",
        params={"host": "web-01", "service": "java"},
    )


@pytest.fixture
def sample_action_critical() -> Action:
    return Action(
        id="act-crit",
        action_type=ActionType.EXECUTE,
        description="Rollback deployment",
        risk_level=RiskLevel.CRITICAL,
        requires_approval=True,
        integration="compute",
        method="restart_service",
        params={"host": "web-01", "service": "deploy"},
    )


@pytest.fixture
def sample_incident(sample_action_low, sample_action_medium) -> Incident:
    return Incident(
        id="INC-001",
        title="High CPU on prod-web-03",
        description="CPU at 94%",
        status=IncidentStatus.DIAGNOSING,
        severity=Severity.HIGH,
        category=ProblemCategory.COMPUTE,
        actions=[sample_action_low, sample_action_medium],
    )


# ---------------------------------------------------------------------------
# create_incident
# ---------------------------------------------------------------------------


class TestCreateIncident:
    @pytest.mark.asyncio
    async def test_creates_incident_with_id(self, orchestrator):
        incident = await orchestrator.create_incident("High CPU on web-03")
        assert incident.id.startswith("INC-")
        assert incident.title == "High CPU on web-03"

    @pytest.mark.asyncio
    async def test_classifies_and_sets_status(self, orchestrator):
        incident = await orchestrator.create_incident("DB connection pool exhausted")
        assert incident.status == IncidentStatus.TRIAGED
        assert incident.classification is not None
        assert incident.severity == Severity.HIGH
        assert incident.category == ProblemCategory.COMPUTE

    @pytest.mark.asyncio
    async def test_adds_timeline_entries(self, orchestrator):
        incident = await orchestrator.create_incident("Problem")
        event_types = [e.event_type for e in incident.timeline]
        assert "created" in event_types
        assert "classified" in event_types

    @pytest.mark.asyncio
    async def test_truncates_long_title(self, orchestrator):
        long_desc = "x" * 200
        incident = await orchestrator.create_incident(long_desc)
        assert len(incident.title) <= 120


# ---------------------------------------------------------------------------
# gather_context
# ---------------------------------------------------------------------------


class TestGatherContext:
    @pytest.mark.asyncio
    async def test_gathers_from_all_providers(self, orchestrator, mock_registry):
        monitoring = AsyncMock()
        monitoring.get_current_alerts = AsyncMock(return_value=[
            Alert(id="a1", name="High CPU", host="web-01", value=94.0,
                  status="triggered", severity=Severity.HIGH),
        ])
        monitoring.get_logs = AsyncMock(return_value=[])
        alerting = AsyncMock()
        alerting.get_active_incidents = AsyncMock(return_value=[])
        ticketing = AsyncMock()
        ticketing.get_recent_changes = AsyncMock(return_value=[])
        compute = AsyncMock()
        compute.get_host_info = AsyncMock(return_value=MagicMock(
            hostname="web-01", model_dump=lambda: {"hostname": "web-01"}))
        compute.get_top_processes = AsyncMock(return_value=[])

        mock_registry.get_provider.side_effect = lambda name: {
            "monitoring": monitoring,
            "alerting": alerting,
            "ticketing": ticketing,
            "compute": compute,
        }[name]

        incident = Incident(
            id="INC-002", title="Test", description="Test",
            status=IncidentStatus.NEW,
        )
        findings = await orchestrator.gather_context(incident)
        assert len(findings) >= 1
        assert incident.status == IncidentStatus.DIAGNOSING

    @pytest.mark.asyncio
    async def test_continues_on_provider_failure(self, orchestrator, mock_registry):
        mock_registry.get_provider.side_effect = Exception("provider unavailable")
        incident = Incident(
            id="INC-003", title="Test", description="Test",
            status=IncidentStatus.NEW,
        )
        # Should not raise
        findings = await orchestrator.gather_context(incident)
        assert findings == []


# ---------------------------------------------------------------------------
# diagnose
# ---------------------------------------------------------------------------


class TestDiagnose:
    @pytest.mark.asyncio
    async def test_returns_diagnostic_result(self, orchestrator, sample_incident):
        result = await orchestrator.diagnose(sample_incident)
        assert result.root_cause == "Memory leak in java process"
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_adds_diagnosed_timeline(self, orchestrator, sample_incident):
        await orchestrator.diagnose(sample_incident)
        event_types = [e.event_type for e in sample_incident.timeline]
        assert "diagnosed" in event_types


# ---------------------------------------------------------------------------
# recommend
# ---------------------------------------------------------------------------


class TestRecommend:
    @pytest.mark.asyncio
    async def test_populates_incident_actions(self, orchestrator):
        incident = Incident(
            id="INC-004", title="Test", description="Test",
            status=IncidentStatus.DIAGNOSING,
        )
        diagnosis = DiagnosticResult(
            root_cause="Memory leak", evidence_summary="CPU spike", confidence=0.8
        )
        await orchestrator.recommend(incident, diagnosis)
        assert len(incident.actions) == 2
        assert incident.status == IncidentStatus.AWAITING_APPROVAL

    @pytest.mark.asyncio
    async def test_action_properties_mapped_correctly(self, orchestrator):
        incident = Incident(
            id="INC-005", title="Test", description="Test",
            status=IncidentStatus.DIAGNOSING,
        )
        diagnosis = DiagnosticResult(
            root_cause="Memory leak", evidence_summary="CPU spike", confidence=0.8
        )
        await orchestrator.recommend(incident, diagnosis)
        medium_action = next(a for a in incident.actions if a.risk_level == RiskLevel.MEDIUM)
        assert medium_action.requires_approval is True
        assert medium_action.integration == "compute"
        assert medium_action.method == "restart_service"


# ---------------------------------------------------------------------------
# Approval gate
# ---------------------------------------------------------------------------


class TestApprovalGate:
    def test_get_pending_approvals_returns_undecided(self, orchestrator, sample_incident):
        pending = orchestrator.get_pending_approvals(sample_incident)
        # Only the medium-risk action requires approval
        assert len(pending) == 1
        assert pending[0].id == "act-med"

    def test_approve_action_single_approver(self, orchestrator, sample_incident):
        action = orchestrator.approve_action(sample_incident, "act-med", "alice")
        assert action is not None
        assert action.approved is True
        assert "alice" in action.approvals

    def test_approve_nonexistent_action_returns_none(self, orchestrator, sample_incident):
        action = orchestrator.approve_action(sample_incident, "no-such-id")
        assert action is None

    def test_reject_action(self, orchestrator, sample_incident):
        action = orchestrator.reject_action(sample_incident, "act-med", "manager")
        assert action is not None
        assert action.approved is False
        assert action.rejected_by == "manager"

    def test_reject_nonexistent_returns_none(self, orchestrator, sample_incident):
        assert orchestrator.reject_action(sample_incident, "no-such-id") is None

    def test_auto_approve_low_risk_only(self, orchestrator, sample_incident):
        auto_approved = orchestrator.auto_approve_low_risk(sample_incident)
        ids = [a.id for a in auto_approved]
        assert "act-low" in ids
        # medium action still pending
        med = next(a for a in sample_incident.actions if a.id == "act-med")
        assert med.approved is None

    def test_approve_adds_timeline_entry(self, orchestrator, sample_incident):
        orchestrator.approve_action(sample_incident, "act-med", "alice")
        event_types = [e.event_type for e in sample_incident.timeline]
        assert any(t in event_types for t in ("approved", "approval_recorded"))

    def test_reject_adds_timeline_entry(self, orchestrator, sample_incident):
        orchestrator.reject_action(sample_incident, "act-med", "manager")
        event_types = [e.event_type for e in sample_incident.timeline]
        assert "rejected" in event_types


class TestMultiApproverPolicy:
    """Verify require_two policy works end-to-end through orchestrator."""

    @pytest.fixture
    def strict_orchestrator(self, settings, mock_registry, mock_ml):
        policy = ApprovalPolicy(critical=ApprovalPolicyType.REQUIRE_TWO)
        return Orchestrator(settings=settings, registry=mock_registry,
                            ml_engine=mock_ml, approval_policy=policy)

    def test_critical_action_needs_two_approvals(self, strict_orchestrator, sample_action_critical):
        incident = Incident(
            id="INC-006", title="Critical", description="Critical",
            status=IncidentStatus.AWAITING_APPROVAL,
            actions=[sample_action_critical],
        )
        # First approval — not yet fully approved
        action = strict_orchestrator.approve_action(incident, "act-crit", "alice")
        assert action.approved is None

        # Second distinct approver — now approved
        action = strict_orchestrator.approve_action(incident, "act-crit", "bob")
        assert action.approved is True

    def test_duplicate_approver_does_not_satisfy_require_two(self, strict_orchestrator, sample_action_critical):
        incident = Incident(
            id="INC-007", title="Critical", description="Critical",
            status=IncidentStatus.AWAITING_APPROVAL,
            actions=[sample_action_critical],
        )
        strict_orchestrator.approve_action(incident, "act-crit", "alice")
        strict_orchestrator.approve_action(incident, "act-crit", "alice")  # duplicate
        assert sample_action_critical.approved is None


# ---------------------------------------------------------------------------
# execute_approved_actions
# ---------------------------------------------------------------------------


class TestExecuteApprovedActions:
    @pytest.mark.asyncio
    async def test_executes_only_approved_actions(self, orchestrator, mock_registry, sample_incident):
        compute = AsyncMock()
        compute.restart_service = AsyncMock(return_value={"status": "ok"})
        mock_registry.get_provider.return_value = compute

        # approve the medium action
        sample_incident.actions[0].approved = True  # low (no integration/method)
        sample_incident.actions[1].approved = True  # medium

        executed = await orchestrator.execute_approved_actions(sample_incident)
        assert len(executed) == 2

    @pytest.mark.asyncio
    async def test_skips_unapproved_actions(self, orchestrator, sample_incident):
        # Only approve the low-risk action (no integration to call)
        sample_incident.actions[0].approved = True

        executed = await orchestrator.execute_approved_actions(sample_incident)
        assert len(executed) == 1
        assert executed[0].id == "act-low"

    @pytest.mark.asyncio
    async def test_handles_provider_error_gracefully(self, orchestrator, mock_registry, sample_incident):
        mock_registry.get_provider.side_effect = Exception("provider down")
        sample_incident.actions[1].approved = True

        executed = await orchestrator.execute_approved_actions(sample_incident)
        failed = next(a for a in executed if a.id == "act-med")
        assert failed.error is not None

    @pytest.mark.asyncio
    async def test_sets_executed_at(self, orchestrator, mock_registry, sample_incident):
        compute = AsyncMock()
        compute.restart_service = AsyncMock(return_value={"status": "ok"})
        mock_registry.get_provider.return_value = compute

        sample_incident.actions[1].approved = True
        await orchestrator.execute_approved_actions(sample_incident)
        assert sample_incident.actions[1].executed_at is not None


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


class TestVerify:
    @pytest.mark.asyncio
    async def test_resolved_when_no_active_alerts(self, orchestrator, mock_registry, sample_incident):
        monitoring = AsyncMock()
        monitoring.get_current_alerts = AsyncMock(return_value=[
            Alert(id="a1", name="Alert", host="web-01", status="resolved", severity=Severity.LOW),
        ])
        mock_registry.get_provider.return_value = monitoring

        result = await orchestrator.verify(sample_incident)
        assert isinstance(result, VerificationResult)
        assert result.resolved is True
        assert sample_incident.status == IncidentStatus.RESOLVED

    @pytest.mark.asyncio
    async def test_not_resolved_when_active_alerts(self, orchestrator, mock_registry, sample_incident):
        monitoring = AsyncMock()
        monitoring.get_current_alerts = AsyncMock(return_value=[
            Alert(id="a1", name="Alert", host="web-01", status="triggered", severity=Severity.HIGH),
        ])
        mock_registry.get_provider.return_value = monitoring

        result = await orchestrator.verify(sample_incident)
        assert result.resolved is False
        assert result.active_alert_count == 1
        assert sample_incident.status == IncidentStatus.VERIFYING

    @pytest.mark.asyncio
    async def test_returns_verification_result_on_error(self, orchestrator, mock_registry, sample_incident):
        mock_registry.get_provider.side_effect = Exception("monitoring unavailable")

        result = await orchestrator.verify(sample_incident)
        assert isinstance(result, VerificationResult)
        assert result.resolved is False
        assert "error" in result.detail.lower()

    @pytest.mark.asyncio
    async def test_attempt_number_recorded(self, orchestrator, mock_registry, sample_incident):
        monitoring = AsyncMock()
        monitoring.get_current_alerts = AsyncMock(return_value=[])
        mock_registry.get_provider.return_value = monitoring

        result = await orchestrator.verify(sample_incident, attempt=3)
        assert result.attempts == 3


# ---------------------------------------------------------------------------
# verify_with_retry
# ---------------------------------------------------------------------------


class TestVerifyWithRetry:
    @pytest.mark.asyncio
    async def test_resolves_on_first_attempt(self, orchestrator, mock_registry, sample_incident):
        monitoring = AsyncMock()
        monitoring.get_current_alerts = AsyncMock(return_value=[])
        mock_registry.get_provider.return_value = monitoring

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await orchestrator.verify_with_retry(
                sample_incident, max_attempts=3, interval_seconds=0
            )
        assert result.resolved is True
        assert result.attempts == 1
        mock_sleep.assert_not_called()  # no sleep needed on first success

    @pytest.mark.asyncio
    async def test_retries_until_resolved(self, orchestrator, mock_registry, sample_incident):
        call_count = 0

        async def flaky_alerts(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return [Alert(id="a1", name="Alert", host="web-01",
                              status="triggered", severity=Severity.HIGH)]
            return []

        monitoring = AsyncMock()
        monitoring.get_current_alerts = flaky_alerts
        mock_registry.get_provider.return_value = monitoring

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await orchestrator.verify_with_retry(
                sample_incident, max_attempts=3, interval_seconds=0
            )
        assert result.resolved is True
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhausts_attempts_and_returns_unresolved(self, orchestrator, mock_registry, sample_incident):
        monitoring = AsyncMock()
        monitoring.get_current_alerts = AsyncMock(return_value=[
            Alert(id="a1", name="Alert", host="web-01",
                  status="triggered", severity=Severity.HIGH),
        ])
        mock_registry.get_provider.return_value = monitoring

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await orchestrator.verify_with_retry(
                sample_incident, max_attempts=2, interval_seconds=0
            )
        assert result.resolved is False


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------


class TestSummarize:
    @pytest.mark.asyncio
    async def test_sets_incident_summary(self, orchestrator, sample_incident):
        summary = await orchestrator.summarize(sample_incident)
        assert summary == "Incident resolved after restarting java service."
        assert sample_incident.summary == summary

    @pytest.mark.asyncio
    async def test_adds_summarized_timeline(self, orchestrator, sample_incident):
        await orchestrator.summarize(sample_incident)
        event_types = [e.event_type for e in sample_incident.timeline]
        assert "summarized" in event_types


# ---------------------------------------------------------------------------
# run_diagnosis (convenience)
# ---------------------------------------------------------------------------


class TestRunDiagnosis:
    @pytest.mark.asyncio
    async def test_returns_incident_with_actions(self, orchestrator, mock_registry):
        monitoring = AsyncMock()
        monitoring.get_current_alerts = AsyncMock(return_value=[])
        monitoring.get_logs = AsyncMock(return_value=[])
        alerting = AsyncMock()
        alerting.get_active_incidents = AsyncMock(return_value=[])
        ticketing = AsyncMock()
        ticketing.get_recent_changes = AsyncMock(return_value=[])
        compute = AsyncMock()
        compute.get_host_info = AsyncMock(return_value=MagicMock(
            hostname="web-01", model_dump=lambda: {"hostname": "web-01"}))
        compute.get_top_processes = AsyncMock(return_value=[])

        mock_registry.get_provider.side_effect = lambda name: {
            "monitoring": monitoring,
            "alerting": alerting,
            "ticketing": ticketing,
            "compute": compute,
        }[name]

        incident = await orchestrator.run_diagnosis("High CPU on web-03")
        assert len(incident.actions) == 2
        # Low-risk action should be auto-approved
        low_action = next(a for a in incident.actions if a.risk_level == RiskLevel.LOW)
        assert low_action.approved is True

    @pytest.mark.asyncio
    async def test_medium_action_not_auto_approved(self, orchestrator, mock_registry):
        for provider in ["monitoring", "alerting", "ticketing", "compute"]:
            pass  # registry will raise, that's fine — gather continues

        mock_registry.get_provider.side_effect = Exception("unavailable")

        incident = await orchestrator.run_diagnosis("DB connection issue")
        medium_action = next(
            (a for a in incident.actions if a.requires_approval and a.risk_level == RiskLevel.MEDIUM),
            None,
        )
        if medium_action:
            assert medium_action.approved is None


# ---------------------------------------------------------------------------
# run_full_workflow
# ---------------------------------------------------------------------------


class TestRunFullWorkflow:
    @pytest.mark.asyncio
    async def test_returns_incident_and_verification(self, orchestrator, mock_registry):
        monitoring = AsyncMock()
        monitoring.get_current_alerts = AsyncMock(return_value=[])
        monitoring.get_logs = AsyncMock(return_value=[])
        alerting = AsyncMock()
        alerting.get_active_incidents = AsyncMock(return_value=[])
        ticketing = AsyncMock()
        ticketing.get_recent_changes = AsyncMock(return_value=[])
        compute = AsyncMock()
        compute.get_host_info = AsyncMock(return_value=MagicMock(
            hostname="web-01", model_dump=lambda: {"hostname": "web-01"}))
        compute.get_top_processes = AsyncMock(return_value=[])
        communication = AsyncMock()
        communication.send_message = AsyncMock(return_value={"status": "sent"})

        mock_registry.get_provider.side_effect = lambda name: {
            "monitoring": monitoring,
            "alerting": alerting,
            "ticketing": ticketing,
            "compute": compute,
            "communication": communication,
        }[name]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            incident, verification = await orchestrator.run_full_workflow(
                "High CPU alert",
                verify_max_attempts=1,
                verify_interval_seconds=0,
            )

        assert isinstance(incident, Incident)
        assert isinstance(verification, VerificationResult)
        assert incident.summary is not None  # summarize was called
