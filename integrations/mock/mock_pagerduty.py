"""Mock PagerDuty provider — implements AlertingProvider with scenario fixtures."""

from __future__ import annotations

from app.config import Settings
from core.models import (
    AlertRequest,
    OnCallInfo,
    PagerIncident,
)
from integrations.base import AlertingProvider
from integrations.mock.base import MockBase


class MockPagerDuty(AlertingProvider, MockBase):
    provider_key = "pagerduty"

    def __init__(self, settings: Settings) -> None:
        MockBase.__init__(self, settings)
        self._acknowledged: set[str] = set()

    async def get_active_incidents(self) -> list[PagerIncident]:
        await self._simulate_delay()
        raw = self._get("incidents", [])
        return [
            PagerIncident(
                id=inc["id"],
                title=inc["title"],
                status="acknowledged" if inc["id"] in self._acknowledged else inc.get("status", "triggered"),
                urgency=inc.get("urgency", "high"),
                service=inc.get("service"),
                assigned_to=inc.get("assigned_to"),
                created_at=inc.get("created_at"),
            )
            for inc in raw
        ]

    async def get_on_call(self, schedule: str) -> OnCallInfo:
        await self._simulate_delay()
        data = self._get("on_call", {})
        return OnCallInfo(
            user=data.get("user", "Unknown"),
            schedule=data.get("schedule", schedule),
            start=data.get("start"),
            end=data.get("end"),
            escalation_level=data.get("escalation_level", 1),
        )

    async def trigger_alert(self, data: AlertRequest) -> None:
        await self._simulate_delay()
        # In mock mode, triggering an alert is a no-op

    async def acknowledge_alert(self, alert_id: str) -> None:
        await self._simulate_delay()
        self._acknowledged.add(alert_id)
