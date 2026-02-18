"""Mock AWS provider — implements ComputeProvider with scenario fixtures."""

from __future__ import annotations

from app.config import Settings
from core.models import (
    HostInfo,
    ProcessInfo,
)
from integrations.base import ComputeProvider
from integrations.mock.base import MockBase


class MockAWS(ComputeProvider, MockBase):
    provider_key = "aws"

    def __init__(self, settings: Settings) -> None:
        MockBase.__init__(self, settings)
        self._restarted_services: list[dict] = []

    async def get_host_info(self, hostname: str) -> HostInfo:
        await self._simulate_delay()
        data = self._get("instance", {})
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
        raw = self._get("top_processes", [])
        return [
            ProcessInfo(
                pid=p["pid"],
                name=p["name"],
                cpu_percent=p.get("cpu_percent", 0.0),
                memory_percent=p.get("memory_percent", 0.0),
                user=p.get("user"),
                command=p.get("command"),
            )
            for p in raw[:limit]
        ]

    async def restart_service(self, hostname: str = "", service: str = "", **kwargs) -> dict:
        # Accept 'host' as alias for 'hostname' (used in ML recommendation params)
        hostname = hostname or kwargs.get("host", "unknown")
        await self._simulate_delay()
        result = {
            "hostname": hostname,
            "service": service,
            "action": "restart",
            "status": "success",
            "message": f"Service '{service}' on {hostname} restarted successfully (mock).",
        }
        self._restarted_services.append(result)
        return result
