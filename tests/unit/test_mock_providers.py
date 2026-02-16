"""Tests for all mock integration providers."""

import pytest

from app.config import Settings
from core.models import (
    CreateIncidentRequest,
    LogQuery,
    MetricQuery,
    ProblemCategory,
    Severity,
    AlertRequest,
)
from integrations.mock.mock_servicenow import MockServiceNow
from integrations.mock.mock_datadog import MockDatadog
from integrations.mock.mock_pagerduty import MockPagerDuty
from integrations.mock.mock_aws import MockAWS
from integrations.mock.mock_slack import MockSlack


@pytest.fixture
def settings():
    return Settings(
        runbook_mode="mock",
        mock_scenario="high_cpu",
        mock_delay_enabled=False,
    )


@pytest.fixture
def db_settings():
    return Settings(
        runbook_mode="mock",
        mock_scenario="database_connection",
        mock_delay_enabled=False,
    )


# ---------------------------------------------------------------------------
# MockServiceNow
# ---------------------------------------------------------------------------


class TestMockServiceNow:
    @pytest.fixture
    def provider(self, settings):
        return MockServiceNow(settings)

    @pytest.mark.asyncio
    async def test_get_incident(self, provider):
        inc = await provider.get_incident("INC0012345")
        assert inc.title == "High CPU on prod-web-03"
        assert inc.severity == Severity.HIGH

    @pytest.mark.asyncio
    async def test_get_recent_changes(self, provider):
        changes = await provider.get_recent_changes("2h")
        assert len(changes) == 2
        assert changes[0].number == "CHG0004567"
        assert changes[0].category == "deployment"

    @pytest.mark.asyncio
    async def test_search_knowledge_base(self, provider):
        articles = await provider.search_knowledge_base("cpu")
        assert len(articles) >= 1
        assert articles[0].relevance_score > 0

    @pytest.mark.asyncio
    async def test_create_incident(self, provider):
        req = CreateIncidentRequest(
            short_description="Test incident",
            severity=Severity.LOW,
            category=ProblemCategory.APPLICATION,
        )
        inc = await provider.create_incident(req)
        assert inc.title == "Test incident"
        assert inc.id.startswith("INC")

    @pytest.mark.asyncio
    async def test_add_work_note(self, provider):
        await provider.add_work_note("INC0012345", "Investigating CPU spike")
        assert "INC0012345" in provider._work_notes
        assert len(provider._work_notes["INC0012345"]) == 1

    @pytest.mark.asyncio
    async def test_scenario_switching(self, db_settings):
        provider = MockServiceNow(db_settings)
        inc = await provider.get_incident("INC0012400")
        assert "database" in inc.title.lower() or "connection" in inc.title.lower()


# ---------------------------------------------------------------------------
# MockDatadog
# ---------------------------------------------------------------------------


class TestMockDatadog:
    @pytest.fixture
    def provider(self, settings):
        return MockDatadog(settings)

    @pytest.mark.asyncio
    async def test_get_current_alerts(self, provider):
        alerts = await provider.get_current_alerts({})
        assert len(alerts) == 2
        assert alerts[0].name == "High CPU Alert"
        assert alerts[0].host == "prod-web-03"

    @pytest.mark.asyncio
    async def test_get_metrics(self, provider):
        ts = await provider.get_metrics(MetricQuery(metric_name="cpu"))
        assert len(ts.points) == 7
        assert ts.points[-1].value == 94.2

    @pytest.mark.asyncio
    async def test_get_metrics_fallback(self, provider):
        """Unknown metric name falls back to first available series."""
        ts = await provider.get_metrics(MetricQuery(metric_name="nonexistent"))
        assert len(ts.points) > 0

    @pytest.mark.asyncio
    async def test_get_logs(self, provider):
        logs = await provider.get_logs(LogQuery(query="*"))
        assert len(logs) == 4
        assert any("OOM" in log.message for log in logs)

    @pytest.mark.asyncio
    async def test_get_host_info(self, provider):
        host = await provider.get_host_info("prod-web-03")
        assert host.hostname == "prod-web-03"
        assert host.instance_type == "c5.xlarge"


# ---------------------------------------------------------------------------
# MockPagerDuty
# ---------------------------------------------------------------------------


class TestMockPagerDuty:
    @pytest.fixture
    def provider(self, settings):
        return MockPagerDuty(settings)

    @pytest.mark.asyncio
    async def test_get_active_incidents(self, provider):
        incidents = await provider.get_active_incidents()
        assert len(incidents) == 1
        assert incidents[0].id == "P1234"
        assert incidents[0].status == "triggered"

    @pytest.mark.asyncio
    async def test_get_on_call(self, provider):
        oc = await provider.get_on_call("Primary On-Call")
        assert oc.user == "Jane Smith"
        assert oc.escalation_level == 1

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, provider):
        await provider.acknowledge_alert("P1234")
        incidents = await provider.get_active_incidents()
        assert incidents[0].status == "acknowledged"

    @pytest.mark.asyncio
    async def test_trigger_alert_noop(self, provider):
        req = AlertRequest(title="Test", description="Test alert")
        await provider.trigger_alert(req)  # should not raise


# ---------------------------------------------------------------------------
# MockAWS
# ---------------------------------------------------------------------------


class TestMockAWS:
    @pytest.fixture
    def provider(self, settings):
        return MockAWS(settings)

    @pytest.mark.asyncio
    async def test_get_host_info(self, provider):
        host = await provider.get_host_info("prod-web-03")
        assert host.hostname == "prod-web-03"
        assert host.instance_id == "i-0abc123def456"

    @pytest.mark.asyncio
    async def test_get_top_processes(self, provider):
        procs = await provider.get_top_processes("prod-web-03", limit=3)
        assert len(procs) == 3
        assert procs[0].name == "java"
        assert procs[0].cpu_percent == 89.3

    @pytest.mark.asyncio
    async def test_get_top_processes_limit(self, provider):
        procs = await provider.get_top_processes("prod-web-03", limit=1)
        assert len(procs) == 1

    @pytest.mark.asyncio
    async def test_restart_service(self, provider):
        result = await provider.restart_service("prod-web-03", "java")
        assert result["status"] == "success"
        assert result["hostname"] == "prod-web-03"
        assert len(provider._restarted_services) == 1


# ---------------------------------------------------------------------------
# MockSlack
# ---------------------------------------------------------------------------


class TestMockSlack:
    @pytest.fixture
    def provider(self, settings):
        return MockSlack(settings)

    @pytest.mark.asyncio
    async def test_get_recent_messages(self, provider):
        msgs = await provider.get_recent_messages("platform-alerts")
        assert len(msgs) == 2
        assert "CPU" in msgs[0].text

    @pytest.mark.asyncio
    async def test_send_message(self, provider):
        await provider.send_message("incidents", "Investigating high CPU issue")
        msgs = await provider.get_recent_messages("incidents")
        assert len(msgs) == 1
        assert msgs[0].author == "runbook-bot"

    @pytest.mark.asyncio
    async def test_create_channel(self, provider):
        ch = await provider.create_channel("inc-12345", "Incident war room")
        assert ch.name == "inc-12345"
        assert ch.purpose == "Incident war room"
        assert ch.id.startswith("C")

    @pytest.mark.asyncio
    async def test_sent_messages_persist_in_session(self, provider):
        await provider.send_message("incidents", "msg1")
        await provider.send_message("incidents", "msg2")
        msgs = await provider.get_recent_messages("incidents")
        assert len(msgs) == 2
        assert msgs[0].text == "msg1"
        assert msgs[1].text == "msg2"
