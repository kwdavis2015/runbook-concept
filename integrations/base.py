"""Abstract base classes for all integration providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.models import (
    Alert,
    AlertRequest,
    Channel,
    ChangeRecord,
    CreateIncidentRequest,
    HostInfo,
    Incident,
    KBArticle,
    LogEntry,
    LogQuery,
    Message,
    MetricQuery,
    MetricTimeSeries,
    OnCallInfo,
    PagerIncident,
    ProcessInfo,
)


class TicketingProvider(ABC):
    """Interface for incident/ticket management systems (ServiceNow, Jira)."""

    @abstractmethod
    async def get_incident(self, incident_id: str) -> Incident:
        ...

    @abstractmethod
    async def create_incident(self, data: CreateIncidentRequest) -> Incident:
        ...

    @abstractmethod
    async def update_incident(self, incident_id: str, updates: dict) -> Incident:
        ...

    @abstractmethod
    async def get_recent_changes(self, timeframe: str) -> list[ChangeRecord]:
        ...

    @abstractmethod
    async def add_work_note(self, incident_id: str, note: str) -> None:
        ...

    @abstractmethod
    async def search_knowledge_base(self, query: str) -> list[KBArticle]:
        ...


class MonitoringProvider(ABC):
    """Interface for monitoring/observability systems (Datadog, CloudWatch)."""

    @abstractmethod
    async def get_current_alerts(self, filters: dict) -> list[Alert]:
        ...

    @abstractmethod
    async def get_metrics(self, query: MetricQuery) -> MetricTimeSeries:
        ...

    @abstractmethod
    async def get_logs(self, query: LogQuery) -> list[LogEntry]:
        ...

    @abstractmethod
    async def get_host_info(self, hostname: str) -> HostInfo:
        ...

    @abstractmethod
    async def get_top_processes(self, hostname: str, limit: int = 10) -> list[ProcessInfo]:
        ...


class AlertingProvider(ABC):
    """Interface for alerting/on-call systems (PagerDuty)."""

    @abstractmethod
    async def get_active_incidents(self) -> list[PagerIncident]:
        ...

    @abstractmethod
    async def get_on_call(self, schedule: str) -> OnCallInfo:
        ...

    @abstractmethod
    async def trigger_alert(self, data: AlertRequest) -> None:
        ...

    @abstractmethod
    async def acknowledge_alert(self, alert_id: str) -> None:
        ...


class ComputeProvider(ABC):
    """Interface for compute/infrastructure systems (AWS EC2, SSH)."""

    @abstractmethod
    async def get_host_info(self, hostname: str) -> HostInfo:
        ...

    @abstractmethod
    async def get_top_processes(self, hostname: str, limit: int = 10) -> list[ProcessInfo]:
        ...

    @abstractmethod
    async def restart_service(self, hostname: str = "", service: str = "", **kwargs) -> dict:
        ...


class CommunicationProvider(ABC):
    """Interface for communication/notification systems (Slack)."""

    @abstractmethod
    async def send_message(self, channel: str, message: str) -> None:
        ...

    @abstractmethod
    async def create_channel(self, name: str, purpose: str) -> Channel:
        ...

    @abstractmethod
    async def get_recent_messages(self, channel: str, limit: int = 50) -> list[Message]:
        ...
