"""Mock Datadog provider — implements MonitoringProvider with scenario fixtures."""

from __future__ import annotations

from app.config import Settings
from core.models import (
    Alert,
    HostInfo,
    LogEntry,
    LogQuery,
    MetricDataPoint,
    MetricQuery,
    MetricTimeSeries,
    ProcessInfo,
    Severity,
)
from integrations.base import MonitoringProvider
from integrations.mock.base import MockBase


class MockDatadog(MonitoringProvider, MockBase):
    provider_key = "datadog"

    def __init__(self, settings: Settings) -> None:
        MockBase.__init__(self, settings)

    async def get_current_alerts(self, filters: dict) -> list[Alert]:
        await self._simulate_delay()
        raw = self._get("alerts", [])
        return [
            Alert(
                id=a["id"],
                name=a["name"],
                host=a.get("host"),
                value=a.get("value"),
                threshold=a.get("threshold"),
                status=a.get("status", "triggered"),
                severity=Severity(a.get("severity", "medium")),
                triggered_at=a.get("triggered_at"),
                tags=a.get("tags", {}),
            )
            for a in raw
        ]

    async def get_metrics(self, query: MetricQuery) -> MetricTimeSeries:
        await self._simulate_delay()
        metrics = self._get("metrics", {})

        # Try exact metric name, then fall back to first available series
        series = metrics.get(query.metric_name, [])
        if not series and metrics:
            series = next(iter(metrics.values()))

        points = [
            MetricDataPoint(timestamp=p["timestamp"], value=p["value"])
            for p in series
        ]
        return MetricTimeSeries(
            metric_name=query.metric_name,
            host=query.host,
            points=points,
        )

    async def get_logs(self, query: LogQuery) -> list[LogEntry]:
        await self._simulate_delay()
        raw = self._get("logs", [])
        return [
            LogEntry(
                timestamp=log["timestamp"],
                level=log.get("level", "info"),
                host=log.get("host"),
                service=log.get("service"),
                message=log["message"],
                attributes=log.get("attributes", {}),
            )
            for log in raw
        ]

    async def get_host_info(self, hostname: str) -> HostInfo:
        await self._simulate_delay()
        data = self._get("host_info", {})
        return HostInfo(
            hostname=data.get("hostname", hostname),
            instance_id=data.get("instance_id"),
            instance_type=data.get("instance_type"),
            state=data.get("state", "running"),
            ip_address=data.get("ip_address"),
            region=data.get("region"),
            tags=data.get("tags", {}),
        )

    async def get_top_processes(self, hostname: str, limit: int = 10) -> list[ProcessInfo]:
        await self._simulate_delay()
        # Datadog monitoring doesn't provide process data in fixture — return empty
        return []
