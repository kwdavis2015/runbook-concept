"""Tests for core data models."""

from datetime import datetime, timezone

from core.models import (
    Action,
    ActionType,
    Alert,
    Classification,
    Finding,
    FindingType,
    Incident,
    IncidentStatus,
    MetricDataPoint,
    MetricTimeSeries,
    ProblemCategory,
    RiskLevel,
    Severity,
    TimelineEntry,
)


class TestEnums:
    def test_severity_values(self):
        assert Severity.LOW == "low"
        assert Severity.CRITICAL == "critical"

    def test_incident_status_values(self):
        assert IncidentStatus.NEW == "new"
        assert IncidentStatus.RESOLVED == "resolved"

    def test_risk_level_values(self):
        assert RiskLevel.LOW == "low"
        assert RiskLevel.CRITICAL == "critical"

    def test_problem_category_values(self):
        assert ProblemCategory.COMPUTE == "compute"
        assert ProblemCategory.UNKNOWN == "unknown"


class TestAlert:
    def test_create_with_required_fields(self):
        alert = Alert(id="a1", name="Test Alert")
        assert alert.id == "a1"
        assert alert.name == "Test Alert"
        assert alert.severity == Severity.MEDIUM
        assert alert.tags == {}

    def test_create_with_all_fields(self):
        alert = Alert(
            id="a1",
            name="High CPU",
            host="web-01",
            value=94.2,
            threshold=90.0,
            status="triggered",
            severity=Severity.HIGH,
            triggered_at=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            tags={"env": "prod"},
        )
        assert alert.host == "web-01"
        assert alert.value == 94.2
        assert alert.tags["env"] == "prod"


class TestClassification:
    def test_defaults(self):
        c = Classification(category=ProblemCategory.COMPUTE, severity=Severity.HIGH)
        assert c.confidence == 0.0
        assert c.reasoning == ""

    def test_full_classification(self):
        c = Classification(
            category=ProblemCategory.NETWORK,
            severity=Severity.CRITICAL,
            confidence=0.95,
            reasoning="Latency spike correlated with CDN change",
        )
        assert c.category == ProblemCategory.NETWORK
        assert c.confidence == 0.95


class TestFinding:
    def test_create(self):
        f = Finding(
            id="f1",
            finding_type=FindingType.ALERT,
            source="datadog",
            summary="High CPU on web-01",
        )
        assert f.finding_type == FindingType.ALERT
        assert f.details == {}


class TestAction:
    def test_defaults(self):
        a = Action(
            id="act1",
            action_type=ActionType.GATHER,
            description="Gather logs",
        )
        assert a.risk_level == RiskLevel.LOW
        assert a.requires_approval is False
        assert a.approved is None
        assert a.result is None

    def test_executable_action(self):
        a = Action(
            id="act2",
            action_type=ActionType.EXECUTE,
            description="Restart service",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            integration="compute",
            method="restart_service",
            params={"host": "web-01", "service": "java"},
        )
        assert a.requires_approval is True
        assert a.params["host"] == "web-01"


class TestTimelineEntry:
    def test_create(self):
        ts = datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc)
        entry = TimelineEntry(
            timestamp=ts,
            event_type="alert",
            summary="CPU alert triggered",
        )
        assert entry.timestamp == ts
        assert entry.source is None


class TestMetricTimeSeries:
    def test_empty_series(self):
        ts = MetricTimeSeries(metric_name="cpu")
        assert ts.points == []
        assert ts.unit is None

    def test_with_points(self):
        points = [
            MetricDataPoint(timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc), value=50.0),
            MetricDataPoint(timestamp=datetime(2026, 1, 15, 10, 15, tzinfo=timezone.utc), value=94.2),
        ]
        ts = MetricTimeSeries(metric_name="cpu", host="web-01", points=points)
        assert len(ts.points) == 2
        assert ts.points[1].value == 94.2


class TestIncident:
    def test_defaults(self):
        inc = Incident(id="INC1", title="Test")
        assert inc.status == IncidentStatus.NEW
        assert inc.severity == Severity.MEDIUM
        assert inc.category == ProblemCategory.UNKNOWN
        assert inc.findings == []
        assert inc.actions == []
        assert inc.timeline == []
        assert inc.classification is None

    def test_full_incident(self, sample_incident):
        """Uses the conftest fixture."""
        assert sample_incident.id == "INC-001"
        assert sample_incident.status == IncidentStatus.DIAGNOSING
        assert len(sample_incident.findings) == 1
        assert len(sample_incident.actions) == 1
        assert len(sample_incident.timeline) == 1
        assert sample_incident.classification.category == ProblemCategory.COMPUTE

    def test_serialization_roundtrip(self):
        inc = Incident(
            id="INC2",
            title="Roundtrip test",
            severity=Severity.HIGH,
            category=ProblemCategory.DATABASE,
        )
        data = inc.model_dump()
        restored = Incident.model_validate(data)
        assert restored.id == inc.id
        assert restored.severity == Severity.HIGH
        assert restored.category == ProblemCategory.DATABASE
