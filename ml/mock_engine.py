"""Mock ML engine — returns scenario-aware canned responses without an API key."""

from __future__ import annotations

import asyncio

from app.config import Settings
from core.models import (
    ActionRecommendation,
    Classification,
    DiagnosticResult,
    Finding,
    Incident,
    ProblemCategory,
    RecommendationSet,
    RiskLevel,
    Severity,
)
from ml.engine import MLEngine

# ---------------------------------------------------------------------------
# Canned responses keyed by scenario name
# ---------------------------------------------------------------------------

_CLASSIFICATIONS: dict[str, Classification] = {
    "high_cpu": Classification(
        category=ProblemCategory.COMPUTE,
        severity=Severity.HIGH,
        confidence=0.94,
        reasoning="CPU usage at 94% on production web server with OOM killer activity indicates a compute resource issue.",
    ),
    "database_connection": Classification(
        category=ProblemCategory.DATABASE,
        severity=Severity.CRITICAL,
        confidence=0.96,
        reasoning="Connection pool at 100% capacity with 'too many connections' errors across multiple services.",
    ),
    "deployment_failure": Classification(
        category=ProblemCategory.DEPLOYMENT,
        severity=Severity.HIGH,
        confidence=0.97,
        reasoning="Partial rollout failure with health check failures on newly deployed instances.",
    ),
    "network_latency": Classification(
        category=ProblemCategory.NETWORK,
        severity=Severity.HIGH,
        confidence=0.92,
        reasoning="Region-specific latency spike (3x normal) affecting EU users while US region remains normal.",
    ),
}

_DIAGNOSES: dict[str, DiagnosticResult] = {
    "high_cpu": DiagnosticResult(
        root_cause="Memory leak in application v2.14.3 deployed 2 hours ago causing excessive garbage collection and CPU consumption.",
        evidence_summary="Java process consuming 89.3% CPU on prod-web-03. GC pauses exceeding 5000ms. OOM killer invoked. CPU spike timing correlates with deployment of v2.14.3 (CHG0004567).",
        confidence=0.91,
        contributing_factors=[
            "Deployment of v2.14.3 introduced memory leak",
            "No memory limit configured for JVM heap",
            "OOM killer creating cascading restarts",
        ],
        affected_components=["prod-web-03", "web-app v2.14.3", "java process"],
    ),
    "database_connection": DiagnosticResult(
        root_cause="Newly deployed inventory-service v1.0.0 is opening database connections without connection pooling, exhausting the pool on db-primary-01.",
        evidence_summary="Connection count jumped from 45 to 200 (max) after inventory-service deployment. Multiple idle postgres connections attributed to inventory-service. Other services (order-service, checkout-service) failing to acquire connections.",
        confidence=0.93,
        contributing_factors=[
            "inventory-service v1.0.0 deployed without connection pooling",
            "No per-service connection limit enforced at database level",
            "Multiple idle connections holding resources",
        ],
        affected_components=["db-primary-01", "inventory-service", "order-service", "checkout-service"],
    ),
    "deployment_failure": DiagnosticResult(
        root_cause="checkout-service v3.1.0 is missing the PAYMENT_GATEWAY_V2_URL environment variable, causing immediate startup failure on new instances.",
        evidence_summary="3 of 8 instances running v3.1.0 crash on startup with 'Required environment variable PAYMENT_GATEWAY_V2_URL is not set'. The variable was added to staging (CHG0004695) but not propagated to production config.",
        confidence=0.97,
        contributing_factors=[
            "Environment variable added to staging but not production",
            "No pre-deployment config validation step",
            "Rolling update continued despite first instance failure",
        ],
        affected_components=["checkout-service", "checkout-pod-06", "checkout-pod-07", "checkout-pod-08"],
    ),
    "network_latency": DiagnosticResult(
        root_cause="CDN routing rule change (CHG0004800) redirected EU traffic through US-East origin instead of EU-West, adding ~4500ms of cross-Atlantic latency.",
        evidence_summary="EU latency jumped from 180ms to 4500ms at 10:30 UTC, exactly when CDN config change was applied. Logs show EU-West edge node routing to us-east-1-origin. US region unaffected. Cache miss rate at 95%.",
        confidence=0.95,
        contributing_factors=[
            "CDN routing rule change for cost optimization",
            "EU origin override pointed to US-East",
            "No latency canary or automated rollback on CDN changes",
        ],
        affected_components=["cdn-eu-west", "api-gateway-eu", "EU user traffic"],
    ),
}

_RECOMMENDATIONS: dict[str, RecommendationSet] = {
    "high_cpu": RecommendationSet(
        summary="Restart the affected service immediately, then plan a rollback of v2.14.3.",
        requires_immediate_action=True,
        recommendations=[
            ActionRecommendation(
                description="Restart the java service on prod-web-03 to relieve immediate CPU pressure",
                risk_level=RiskLevel.MEDIUM,
                requires_approval=True,
                integration="compute",
                method="restart_service",
                params={"host": "prod-web-03", "service": "java"},
                reasoning="Immediate relief while rollback is prepared. Service restart is lower risk than full rollback.",
            ),
            ActionRecommendation(
                description="Roll back deployment from v2.14.3 to v2.14.2",
                risk_level=RiskLevel.HIGH,
                requires_approval=True,
                integration="compute",
                method="restart_service",
                params={"host": "prod-web-03", "service": "java", "version": "2.14.2"},
                reasoning="Permanent fix — removes the code with the memory leak.",
            ),
            ActionRecommendation(
                description="Notify the platform-alerts Slack channel about the incident",
                risk_level=RiskLevel.LOW,
                requires_approval=False,
                integration="communication",
                method="send_message",
                params={"channel": "platform-alerts", "message": "Investigating high CPU on prod-web-03. Service restart in progress."},
                reasoning="Keep the team informed during incident response.",
            ),
        ],
    ),
    "database_connection": RecommendationSet(
        summary="Restart inventory-service with connection pooling enabled, and temporarily increase max_connections.",
        requires_immediate_action=True,
        recommendations=[
            ActionRecommendation(
                description="Restart inventory-service with connection pooling configured (pool_size=10)",
                risk_level=RiskLevel.MEDIUM,
                requires_approval=True,
                integration="compute",
                method="restart_service",
                params={"host": "inventory-service", "service": "inventory-service", "config": {"pool_size": 10}},
                reasoning="Fixes the root cause — inventory-service will reuse connections instead of opening new ones.",
            ),
            ActionRecommendation(
                description="Temporarily increase database max_connections from 200 to 300",
                risk_level=RiskLevel.MEDIUM,
                requires_approval=True,
                integration="compute",
                method="restart_service",
                params={"host": "db-primary-01", "service": "postgresql", "config": {"max_connections": 300}},
                reasoning="Provides immediate headroom while inventory-service is being fixed.",
            ),
            ActionRecommendation(
                description="Notify database-alerts Slack channel",
                risk_level=RiskLevel.LOW,
                requires_approval=False,
                integration="communication",
                method="send_message",
                params={"channel": "database-alerts", "message": "DB connection exhaustion on db-primary-01 — root cause identified as inventory-service. Fix in progress."},
                reasoning="Keep the database team informed.",
            ),
        ],
    ),
    "deployment_failure": RecommendationSet(
        summary="Roll back checkout-service to v3.0.9, then add the missing environment variable to production config.",
        requires_immediate_action=True,
        recommendations=[
            ActionRecommendation(
                description="Roll back checkout-service from v3.1.0 to v3.0.9",
                risk_level=RiskLevel.HIGH,
                requires_approval=True,
                integration="compute",
                method="restart_service",
                params={"host": "checkout-service", "service": "checkout-service", "version": "3.0.9"},
                reasoning="Restores all 8 instances to the last known good version.",
            ),
            ActionRecommendation(
                description="Add PAYMENT_GATEWAY_V2_URL to production environment config",
                risk_level=RiskLevel.LOW,
                requires_approval=False,
                integration=None,
                method=None,
                params={},
                reasoning="Required before re-attempting the v3.1.0 deployment.",
            ),
            ActionRecommendation(
                description="Notify deploy-notifications Slack channel",
                risk_level=RiskLevel.LOW,
                requires_approval=False,
                integration="communication",
                method="send_message",
                params={"channel": "deploy-notifications", "message": "Rolling back checkout-service v3.1.0 → v3.0.9 due to missing env var. Details in incident channel."},
                reasoning="Keep the team informed of rollback status.",
            ),
        ],
    ),
    "network_latency": RecommendationSet(
        summary="Revert the CDN routing configuration change to restore EU traffic to EU-West origin.",
        requires_immediate_action=True,
        recommendations=[
            ActionRecommendation(
                description="Revert CDN routing rule change (CHG0004800) to restore EU-West origin",
                risk_level=RiskLevel.MEDIUM,
                requires_approval=True,
                integration="compute",
                method="restart_service",
                params={"host": "cdn-eu-west", "service": "cdn", "config": {"origin": "eu-west-1-origin.example.com"}},
                reasoning="Directly reverses the misconfiguration causing EU latency.",
            ),
            ActionRecommendation(
                description="Flush CDN cache for EU region to ensure fresh content from correct origin",
                risk_level=RiskLevel.LOW,
                requires_approval=False,
                integration="compute",
                method="restart_service",
                params={"host": "cdn-eu-west", "service": "varnish"},
                reasoning="Cache may contain stale entries routed through US-East.",
            ),
            ActionRecommendation(
                description="Notify infra-alerts Slack channel",
                risk_level=RiskLevel.LOW,
                requires_approval=False,
                integration="communication",
                method="send_message",
                params={"channel": "infra-alerts", "message": "EU latency issue identified — CDN routing misconfiguration. Reverting CHG0004800."},
                reasoning="Keep infrastructure team informed.",
            ),
        ],
    ),
}

_SUMMARIES: dict[str, str] = {
    "high_cpu": (
        "At approximately 10:28 UTC on January 15, a high CPU alert was triggered on "
        "prod-web-03 with CPU utilization reaching 94.2%. The monitoring system also "
        "detected elevated memory usage at 87.5%.\n\n"
        "Investigation revealed that the Java application process (PID 12345) was "
        "consuming 89.3% of CPU. The OOM killer had been invoked, and GC pauses "
        "exceeded 5000ms, indicating a severe memory leak. A review of recent changes "
        "identified deployment CHG0004567 (application v2.14.3) completed at 08:45 UTC, "
        "approximately 2 hours before the CPU spike began.\n\n"
        "The root cause was determined to be a memory leak introduced in v2.14.3. "
        "The recommended actions were to restart the affected service for immediate "
        "relief and plan a rollback to v2.14.2 to permanently resolve the issue."
    ),
    "database_connection": (
        "At approximately 14:08 UTC on January 20, a critical alert fired indicating "
        "that database connections on db-primary-01 had reached 100% capacity (200/200). "
        "Multiple application services including order-service and checkout-service began "
        "reporting 'too many connections' errors.\n\n"
        "Investigation traced the connection exhaustion to the newly deployed "
        "inventory-service v1.0.0 (CHG0004600, deployed at 13:00 UTC). The service was "
        "opening direct database connections without connection pooling configured, "
        "rapidly consuming available connections.\n\n"
        "The recommended resolution was to restart inventory-service with connection "
        "pooling enabled (pool_size=10) and temporarily increase max_connections to 300 "
        "to provide headroom during the fix."
    ),
    "deployment_failure": (
        "At approximately 16:42 UTC on January 22, health check failures were detected "
        "on checkout-service instances running the newly deployed v3.1.0. The rolling "
        "update had progressed to 3 of 8 instances, all of which were crashing on startup.\n\n"
        "Log analysis revealed that all three failing instances exited immediately with "
        "'Required environment variable PAYMENT_GATEWAY_V2_URL is not set'. A review of "
        "recent changes showed that CHG0004695 had added this variable to the staging "
        "environment, but it was never propagated to the production configuration.\n\n"
        "The recommended action was an immediate rollback to v3.0.9 to restore all "
        "instances to a healthy state, followed by adding the missing environment variable "
        "to production config before re-attempting the deployment."
    ),
    "network_latency": (
        "Starting at approximately 10:30 UTC on January 25, users in the EU region "
        "began experiencing page load times of 4-5 seconds, roughly 3x the normal "
        "latency of 180ms. The US region was completely unaffected.\n\n"
        "Investigation revealed that CDN routing configuration change CHG0004800, "
        "applied at 10:30 UTC for cost optimization, had overridden the EU-West origin "
        "to point to us-east-1-origin.example.com. This forced all EU traffic to cross "
        "the Atlantic to reach US-East servers. CDN cache miss rates spiked to 95%.\n\n"
        "The recommended resolution was to immediately revert the CDN routing rule "
        "to restore EU-West as the origin for EU traffic, and flush the CDN cache to "
        "clear any stale entries."
    ),
}

# Default fallbacks for unknown scenarios
_DEFAULT_CLASSIFICATION = Classification(
    category=ProblemCategory.UNKNOWN,
    severity=Severity.MEDIUM,
    confidence=0.5,
    reasoning="Unable to classify — scenario not recognized by mock engine.",
)

_DEFAULT_DIAGNOSIS = DiagnosticResult(
    root_cause="Unknown — mock engine does not have canned data for this scenario.",
    evidence_summary="No scenario-specific evidence available.",
    confidence=0.0,
)

_DEFAULT_RECOMMENDATIONS = RecommendationSet(
    summary="No specific recommendations — scenario not recognized by mock engine.",
)


class MockMLEngine(MLEngine):
    """Scenario-aware mock ML engine that returns canned responses."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def _scenario(self) -> str:
        return self._settings.mock_scenario

    async def classify(self, problem_description: str) -> Classification:
        await asyncio.sleep(0.1)  # Brief delay for realism
        return _CLASSIFICATIONS.get(self._scenario, _DEFAULT_CLASSIFICATION)

    async def diagnose(
        self,
        problem_description: str,
        findings: list[Finding],
    ) -> DiagnosticResult:
        await asyncio.sleep(0.2)
        return _DIAGNOSES.get(self._scenario, _DEFAULT_DIAGNOSIS)

    async def recommend(
        self,
        problem_description: str,
        diagnosis: DiagnosticResult,
        findings: list[Finding],
    ) -> RecommendationSet:
        await asyncio.sleep(0.2)
        return _RECOMMENDATIONS.get(self._scenario, _DEFAULT_RECOMMENDATIONS)

    async def summarize(self, incident: Incident) -> str:
        await asyncio.sleep(0.1)
        return _SUMMARIES.get(self._scenario, "No summary available for this scenario.")
