"""Core data models for the Runbook Concept application."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    NEW = "new"
    TRIAGED = "triaged"
    DIAGNOSING = "diagnosing"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    CLOSED = "closed"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionType(str, Enum):
    GATHER = "gather"
    ML_DECISION = "ml_decision"
    EXECUTE = "execute"
    NOTIFY = "notify"


class ProblemCategory(str, Enum):
    COMPUTE = "compute"
    NETWORK = "network"
    DATABASE = "database"
    DEPLOYMENT = "deployment"
    STORAGE = "storage"
    SECURITY = "security"
    APPLICATION = "application"
    UNKNOWN = "unknown"


class FindingType(str, Enum):
    ALERT = "alert"
    METRIC_ANOMALY = "metric_anomaly"
    LOG_PATTERN = "log_pattern"
    CONFIGURATION = "configuration"
    RECENT_CHANGE = "recent_change"
    CORRELATION = "correlation"


# ---------------------------------------------------------------------------
# Integration data models
# ---------------------------------------------------------------------------


class Alert(BaseModel):
    id: str
    name: str
    host: str | None = None
    value: float | None = None
    threshold: float | None = None
    status: str = "triggered"
    severity: Severity = Severity.MEDIUM
    triggered_at: datetime | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class MetricQuery(BaseModel):
    metric_name: str
    host: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    start: datetime | None = None
    end: datetime | None = None


class MetricDataPoint(BaseModel):
    timestamp: datetime
    value: float


class MetricTimeSeries(BaseModel):
    metric_name: str
    host: str | None = None
    points: list[MetricDataPoint] = Field(default_factory=list)
    unit: str | None = None


class LogQuery(BaseModel):
    query: str
    host: str | None = None
    service: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    limit: int = 100


class LogEntry(BaseModel):
    timestamp: datetime
    level: str = "info"
    host: str | None = None
    service: str | None = None
    message: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class HostInfo(BaseModel):
    hostname: str
    instance_id: str | None = None
    instance_type: str | None = None
    state: str = "running"
    ip_address: str | None = None
    region: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class ProcessInfo(BaseModel):
    pid: int
    name: str
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    user: str | None = None
    command: str | None = None


class ChangeRecord(BaseModel):
    id: str
    number: str
    description: str
    status: str = "closed"
    created_at: datetime | None = None
    closed_at: datetime | None = None
    requested_by: str | None = None
    category: str | None = None


class KBArticle(BaseModel):
    id: str
    title: str
    content: str
    category: str | None = None
    relevance_score: float = 0.0


class PagerIncident(BaseModel):
    id: str
    title: str
    status: str = "triggered"
    urgency: str = "high"
    service: str | None = None
    assigned_to: str | None = None
    created_at: datetime | None = None


class OnCallInfo(BaseModel):
    user: str
    schedule: str
    start: datetime | None = None
    end: datetime | None = None
    escalation_level: int = 1


class AlertRequest(BaseModel):
    title: str
    description: str
    severity: Severity = Severity.HIGH
    service: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class Channel(BaseModel):
    id: str
    name: str
    purpose: str = ""
    created_at: datetime | None = None


class Message(BaseModel):
    id: str
    channel: str
    text: str
    author: str
    timestamp: datetime | None = None


class CreateIncidentRequest(BaseModel):
    short_description: str
    description: str = ""
    severity: Severity = Severity.MEDIUM
    category: ProblemCategory = ProblemCategory.UNKNOWN
    assigned_to: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core domain models
# ---------------------------------------------------------------------------


class Finding(BaseModel):
    """A piece of evidence discovered during diagnosis."""

    id: str
    finding_type: FindingType
    source: str
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    timestamp: datetime | None = None


class Action(BaseModel):
    """A recommended or executed action."""

    id: str
    action_type: ActionType
    description: str
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    approved: bool | None = None
    approved_by: str | None = None
    integration: str | None = None
    method: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    executed_at: datetime | None = None
    error: str | None = None


class TimelineEntry(BaseModel):
    """A single entry in the incident timeline."""

    timestamp: datetime
    event_type: str
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None


class Classification(BaseModel):
    """Result of ML problem classification."""

    category: ProblemCategory
    severity: Severity
    confidence: float = 0.0
    reasoning: str = ""


class ActionRecommendation(BaseModel):
    """A single recommended action from the ML engine."""

    description: str
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    integration: str | None = None
    method: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""


class DiagnosticResult(BaseModel):
    """Output of the ML diagnostic analyzer."""

    root_cause: str
    evidence_summary: str
    confidence: float = 0.0
    contributing_factors: list[str] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)


class RecommendationSet(BaseModel):
    """A ranked set of action recommendations from the ML engine."""

    recommendations: list[ActionRecommendation] = Field(default_factory=list)
    summary: str = ""
    requires_immediate_action: bool = False


class Incident(BaseModel):
    """Top-level incident tracking all diagnostic activity."""

    id: str
    title: str
    description: str = ""
    status: IncidentStatus = IncidentStatus.NEW
    severity: Severity = Severity.MEDIUM
    category: ProblemCategory = ProblemCategory.UNKNOWN
    classification: Classification | None = None
    findings: list[Finding] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    timeline: list[TimelineEntry] = Field(default_factory=list)
    created_at: datetime | None = None
    resolved_at: datetime | None = None
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
