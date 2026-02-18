"""Orchestrator — central workflow engine connecting ML, integrations, and human approval."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from core.approval import ApprovalEvaluator, ApprovalPolicy
from core.models import (
    Action,
    ActionRecommendation,
    ActionType,
    DiagnosticResult,
    Finding,
    FindingType,
    Incident,
    IncidentStatus,
    LogQuery,
    MetricQuery,
    RecommendationSet,
    RiskLevel,
    TimelineEntry,
    VerificationResult,
)
from integrations.registry import IntegrationRegistry
from ml.engine import MLEngine

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid() -> str:
    return uuid.uuid4().hex[:8]


class Orchestrator:
    """Central coordinator for the incident diagnostic workflow.

    Lifecycle: classify → gather → diagnose → recommend → gate → execute → verify → document
    """

    def __init__(
        self,
        settings: Settings,
        registry: IntegrationRegistry,
        ml_engine: MLEngine,
        approval_policy: ApprovalPolicy | None = None,
    ) -> None:
        self._settings = settings
        self._registry = registry
        self._ml = ml_engine
        self._evaluator = ApprovalEvaluator(approval_policy or ApprovalPolicy())

    # ------------------------------------------------------------------
    # Timeline helper
    # ------------------------------------------------------------------

    @staticmethod
    def _add_timeline(
        incident: Incident,
        event_type: str,
        summary: str,
        source: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        incident.timeline.append(
            TimelineEntry(
                timestamp=_now(),
                event_type=event_type,
                summary=summary,
                source=source,
                details=details or {},
            )
        )

    # ------------------------------------------------------------------
    # 1. Create & classify
    # ------------------------------------------------------------------

    async def create_incident(self, problem_description: str) -> Incident:
        """Create a new incident from a problem description and classify it."""
        incident = Incident(
            id=f"INC-{_uid()}",
            title=problem_description[:120],
            description=problem_description,
            status=IncidentStatus.NEW,
            created_at=_now(),
        )
        self._add_timeline(incident, "created", "Incident created from user report")

        # Classify
        incident.status = IncidentStatus.TRIAGED
        classification = await self._ml.classify(problem_description)
        incident.classification = classification
        incident.severity = classification.severity
        incident.category = classification.category
        self._add_timeline(
            incident,
            "classified",
            f"Classified as {classification.category} / {classification.severity} "
            f"(confidence: {classification.confidence:.0%})",
            source="ml_engine",
            details={"reasoning": classification.reasoning},
        )

        return incident

    # ------------------------------------------------------------------
    # 2. Gather context
    # ------------------------------------------------------------------

    async def gather_context(self, incident: Incident) -> list[Finding]:
        """Query integrations to gather operational evidence."""
        incident.status = IncidentStatus.DIAGNOSING
        self._add_timeline(incident, "gathering", "Gathering context from integrations")
        findings: list[Finding] = []

        # Monitoring — alerts
        try:
            monitoring = self._registry.get_provider("monitoring")
            alerts = await monitoring.get_current_alerts({})
            for alert in alerts:
                finding = Finding(
                    id=f"find-{_uid()}",
                    finding_type=FindingType.ALERT,
                    source="monitoring",
                    summary=f"[{alert.severity}] {alert.name} on {alert.host or 'unknown'} "
                            f"(value: {alert.value})",
                    details=alert.model_dump(),
                    confidence=0.9,
                    timestamp=_now(),
                )
                findings.append(finding)
        except Exception as e:
            logger.warning("Failed to gather alerts: %s", e)

        # Monitoring — logs
        try:
            monitoring = self._registry.get_provider("monitoring")
            logs = await monitoring.get_logs(LogQuery(query="*"))
            if logs:
                finding = Finding(
                    id=f"find-{_uid()}",
                    finding_type=FindingType.LOG_PATTERN,
                    source="monitoring",
                    summary=f"{len(logs)} log entries gathered",
                    details={"entries": [l.model_dump() for l in logs[:10]]},
                    confidence=0.7,
                    timestamp=_now(),
                )
                findings.append(finding)
        except Exception as e:
            logger.warning("Failed to gather logs: %s", e)

        # Ticketing — recent changes
        try:
            ticketing = self._registry.get_provider("ticketing")
            changes = await ticketing.get_recent_changes("4h")
            for change in changes:
                finding = Finding(
                    id=f"find-{_uid()}",
                    finding_type=FindingType.RECENT_CHANGE,
                    source="ticketing",
                    summary=f"Change {change.number}: {change.description}",
                    details=change.model_dump(),
                    confidence=0.8,
                    timestamp=_now(),
                )
                findings.append(finding)
        except Exception as e:
            logger.warning("Failed to gather changes: %s", e)

        # Compute — top processes
        try:
            compute = self._registry.get_provider("compute")
            host_info = await compute.get_host_info("")
            processes = await compute.get_top_processes(host_info.hostname, limit=5)
            if processes:
                finding = Finding(
                    id=f"find-{_uid()}",
                    finding_type=FindingType.METRIC_ANOMALY,
                    source="compute",
                    summary=f"Top process: {processes[0].name} at {processes[0].cpu_percent}% CPU "
                            f"on {host_info.hostname}",
                    details={
                        "host": host_info.model_dump(),
                        "processes": [p.model_dump() for p in processes],
                    },
                    confidence=0.85,
                    timestamp=_now(),
                )
                findings.append(finding)
        except Exception as e:
            logger.warning("Failed to gather compute data: %s", e)

        # Alerting — on-call & PagerDuty incidents
        try:
            alerting = self._registry.get_provider("alerting")
            pager_incidents = await alerting.get_active_incidents()
            for pi in pager_incidents:
                finding = Finding(
                    id=f"find-{_uid()}",
                    finding_type=FindingType.ALERT,
                    source="alerting",
                    summary=f"PagerDuty: {pi.title} (status: {pi.status})",
                    details=pi.model_dump(),
                    confidence=0.9,
                    timestamp=_now(),
                )
                findings.append(finding)
        except Exception as e:
            logger.warning("Failed to gather alerting data: %s", e)

        incident.findings = findings
        self._add_timeline(
            incident,
            "context_gathered",
            f"Gathered {len(findings)} findings from integrations",
        )
        return findings

    # ------------------------------------------------------------------
    # 3. Diagnose
    # ------------------------------------------------------------------

    async def diagnose(self, incident: Incident) -> DiagnosticResult:
        """Run ML diagnosis over gathered findings."""
        self._add_timeline(incident, "diagnosing", "Running ML diagnosis")

        diagnosis = await self._ml.diagnose(incident.description, incident.findings)

        self._add_timeline(
            incident,
            "diagnosed",
            f"Root cause: {diagnosis.root_cause} (confidence: {diagnosis.confidence:.0%})",
            source="ml_engine",
            details={
                "contributing_factors": diagnosis.contributing_factors,
                "affected_components": diagnosis.affected_components,
            },
        )
        return diagnosis

    # ------------------------------------------------------------------
    # 4. Recommend
    # ------------------------------------------------------------------

    async def recommend(
        self, incident: Incident, diagnosis: DiagnosticResult
    ) -> RecommendationSet:
        """Generate action recommendations from the ML engine."""
        rec_set = await self._ml.recommend(
            incident.description, diagnosis, incident.findings
        )

        # Convert recommendations into Action objects on the incident
        for i, rec in enumerate(rec_set.recommendations):
            action = self._recommendation_to_action(rec, i)
            incident.actions.append(action)

        incident.status = IncidentStatus.AWAITING_APPROVAL
        self._add_timeline(
            incident,
            "recommended",
            f"{len(rec_set.recommendations)} actions recommended — {rec_set.summary}",
            source="ml_engine",
        )
        return rec_set

    @staticmethod
    def _recommendation_to_action(rec: ActionRecommendation, index: int) -> Action:
        return Action(
            id=f"act-{_uid()}",
            action_type=ActionType.EXECUTE if rec.integration else ActionType.NOTIFY,
            description=rec.description,
            risk_level=rec.risk_level,
            requires_approval=rec.requires_approval,
            integration=rec.integration,
            method=rec.method,
            params=rec.params,
        )

    # ------------------------------------------------------------------
    # 5. Approval gate
    # ------------------------------------------------------------------

    def get_pending_approvals(self, incident: Incident) -> list[Action]:
        """Return actions that require human approval and haven't been decided yet."""
        return self._evaluator.get_pending_approvals(incident.actions)

    def approve_action(self, incident: Incident, action_id: str, approved_by: str = "operator") -> Action | None:
        """Record an approval for a specific action.

        Supports multi-approver policies: the action's ``approved`` flag is set
        to True only once the policy threshold is met. Returns the action, or
        None if not found.
        """
        for action in incident.actions:
            if action.id == action_id:
                now_approved = self._evaluator.add_approval(action, approved_by)
                summary = (
                    f"Action fully approved: {action.description}"
                    if now_approved
                    else f"Approval recorded ({len(action.approvals)} of "
                         f"{self._evaluator.minimum_approvals_needed(action)} needed): "
                         f"{action.description}"
                )
                self._add_timeline(
                    incident,
                    "approved" if now_approved else "approval_recorded",
                    summary,
                    details={"action_id": action_id, "approved_by": approved_by,
                             "approvals": action.approvals},
                )
                return action
        return None

    def reject_action(self, incident: Incident, action_id: str, rejected_by: str = "operator") -> Action | None:
        """Reject a specific action."""
        for action in incident.actions:
            if action.id == action_id:
                self._evaluator.reject(action, rejected_by)
                self._add_timeline(
                    incident,
                    "rejected",
                    f"Action rejected: {action.description}",
                    details={"action_id": action_id, "rejected_by": rejected_by},
                )
                return action
        return None

    def auto_approve_low_risk(self, incident: Incident) -> list[Action]:
        """Auto-approve all actions that the policy does not require human approval for."""
        auto_approved = self._evaluator.apply_auto_approvals(incident.actions)
        for action in auto_approved:
            self._add_timeline(
                incident,
                "auto_approved",
                f"Auto-approved (policy: auto): {action.description}",
            )
        return auto_approved

    # ------------------------------------------------------------------
    # 6. Execute
    # ------------------------------------------------------------------

    async def execute_approved_actions(self, incident: Incident) -> list[Action]:
        """Execute all approved actions that haven't been executed yet."""
        incident.status = IncidentStatus.EXECUTING
        executed = []

        for action in incident.actions:
            if action.approved and action.executed_at is None:
                result = await self._execute_single_action(action)
                executed.append(action)
                self._add_timeline(
                    incident,
                    "executed",
                    f"Executed: {action.description} — {'success' if not action.error else 'failed'}",
                    details=result,
                )

        return executed

    async def _execute_single_action(self, action: Action) -> dict:
        """Execute a single action via the integration layer."""
        if not action.integration or not action.method:
            action.executed_at = _now()
            action.result = {"status": "skipped", "reason": "No integration/method specified"}
            return action.result

        try:
            provider = self._registry.get_provider(action.integration)
            method = getattr(provider, action.method, None)
            if method is None:
                action.executed_at = _now()
                action.error = f"Method '{action.method}' not found on {action.integration} provider"
                return {"status": "error", "error": action.error}

            result = await method(**action.params)
            action.executed_at = _now()
            action.result = result if isinstance(result, dict) else {"result": str(result)}
            return action.result
        except Exception as e:
            action.executed_at = _now()
            action.error = str(e)
            logger.error("Action execution failed: %s", e)
            return {"status": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # 7. Verify
    # ------------------------------------------------------------------

    async def verify(self, incident: Incident, attempt: int = 1) -> VerificationResult:
        """Re-query integrations to check if the problem is resolved.

        Uses alert count as a simple heuristic: zero active alerts → resolved.
        Returns a VerificationResult with counts and resolution status.
        """
        incident.status = IncidentStatus.VERIFYING
        self._add_timeline(incident, "verifying", f"Verification attempt {attempt}")

        try:
            monitoring = self._registry.get_provider("monitoring")
            alerts = await monitoring.get_current_alerts({})
            active = [a for a in alerts if a.status == "triggered"]
            cleared = [a for a in alerts if a.status != "triggered"]
            resolved = len(active) == 0

            result = VerificationResult(
                resolved=resolved,
                active_alert_count=len(active),
                cleared_alert_count=len(cleared),
                attempts=attempt,
                detail="No active alerts" if resolved else f"{len(active)} alerts still firing",
            )

            if resolved:
                incident.status = IncidentStatus.RESOLVED
                incident.resolved_at = _now()
                self._add_timeline(incident, "resolved", "Verification passed — no active alerts")
            else:
                self._add_timeline(
                    incident,
                    "verification_failed",
                    f"Attempt {attempt}: {len(active)} alerts still active",
                )
            return result
        except Exception as e:
            logger.warning("Verification error: %s", e)
            self._add_timeline(incident, "verification_error", f"Verification error: {e}")
            return VerificationResult(
                resolved=False,
                attempts=attempt,
                detail=f"Verification error: {e}",
            )

    async def verify_with_retry(
        self,
        incident: Incident,
        max_attempts: int = 3,
        interval_seconds: float = 30.0,
    ) -> VerificationResult:
        """Retry verification up to *max_attempts* times with a delay between each.

        Returns the first successful VerificationResult, or the final failed
        result after exhausting all attempts.
        """
        result = VerificationResult(resolved=False)
        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                await asyncio.sleep(interval_seconds)
            result = await self.verify(incident, attempt=attempt)
            if result.resolved:
                break
        return result

    # ------------------------------------------------------------------
    # 8. Document / summarize
    # ------------------------------------------------------------------

    async def summarize(self, incident: Incident) -> str:
        """Generate a narrative summary of the incident."""
        summary = await self._ml.summarize(incident)
        incident.summary = summary
        self._add_timeline(incident, "summarized", "Incident summary generated", source="ml_engine")
        return summary

    # ------------------------------------------------------------------
    # Full workflow (convenience)
    # ------------------------------------------------------------------

    async def run_diagnosis(self, problem_description: str) -> Incident:
        """Run the full diagnostic workflow up to the recommendation stage.

        Steps: create → classify → gather → diagnose → recommend → auto-approve low-risk.
        Returns the incident in AWAITING_APPROVAL status with actions populated.
        """
        incident = await self.create_incident(problem_description)
        await self.gather_context(incident)
        diagnosis = await self.diagnose(incident)
        await self.recommend(incident, diagnosis)
        self.auto_approve_low_risk(incident)
        return incident

    async def run_full_workflow(
        self,
        problem_description: str,
        verify_max_attempts: int = 3,
        verify_interval_seconds: float = 30.0,
    ) -> tuple[Incident, VerificationResult]:
        """End-to-end workflow: diagnose → execute approved actions → verify → summarize.

        All actions that auto-qualify are executed immediately. Actions that require
        human approval are left pending (AWAITING_APPROVAL status). Only approved
        actions are executed.

        Steps:
            1. run_diagnosis — create, classify, gather, diagnose, recommend, auto-approve
            2. execute_approved_actions — run all auto-approved actions
            3. verify_with_retry — confirm resolution
            4. summarize — generate narrative

        Returns:
            (incident, verification_result)
        """
        incident = await self.run_diagnosis(problem_description)
        await self.execute_approved_actions(incident)
        verification = await self.verify_with_retry(
            incident,
            max_attempts=verify_max_attempts,
            interval_seconds=verify_interval_seconds,
        )
        await self.summarize(incident)
        return incident, verification
