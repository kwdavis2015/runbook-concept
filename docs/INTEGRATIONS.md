# Integration Guide

## Overview

Runbook Concept connects to external tools through a provider abstraction layer. Each integration category has an abstract base class, and concrete implementations exist for both mock and real services.

## Integration Categories

| Category | Purpose | Mock Provider | Real Providers |
|----------|---------|---------------|----------------|
| **Ticketing** | Incident management, change records | MockServiceNow | ServiceNow, Jira |
| **Monitoring** | Metrics, alerts, dashboards | MockDatadog | Datadog, CloudWatch |
| **Alerting** | On-call schedules, escalation | MockPagerDuty | PagerDuty |
| **Compute** | Server management, process info | MockAWS | AWS EC2, SSH |
| **Logging** | Log search, analysis | MockDatadog | Datadog Logs, CloudWatch Logs |
| **Communication** | Notifications, war rooms | MockSlack | Slack |

## Abstract Interfaces

### TicketingProvider

```python
class TicketingProvider(ABC):
    async def get_incident(self, incident_id: str) -> Incident
    async def create_incident(self, data: CreateIncidentRequest) -> Incident
    async def update_incident(self, incident_id: str, updates: dict) -> Incident
    async def get_recent_changes(self, timeframe: str) -> list[ChangeRecord]
    async def add_work_note(self, incident_id: str, note: str) -> None
    async def search_knowledge_base(self, query: str) -> list[KBArticle]
```

### MonitoringProvider

```python
class MonitoringProvider(ABC):
    async def get_current_alerts(self, filters: dict) -> list[Alert]
    async def get_metrics(self, query: MetricQuery) -> MetricTimeSeries
    async def get_host_info(self, hostname: str) -> HostInfo
    async def get_top_processes(self, hostname: str, limit: int) -> list[ProcessInfo]
```

### AlertingProvider

```python
class AlertingProvider(ABC):
    async def get_active_incidents(self) -> list[PagerIncident]
    async def get_on_call(self, schedule: str) -> OnCallInfo
    async def trigger_alert(self, data: AlertRequest) -> None
    async def acknowledge_alert(self, alert_id: str) -> None
```

### CommunicationProvider

```python
class CommunicationProvider(ABC):
    async def send_message(self, channel: str, message: str) -> None
    async def create_channel(self, name: str, purpose: str) -> Channel
    async def get_recent_messages(self, channel: str, limit: int) -> list[Message]
```

## Adding a New Real Integration

1. **Create a new provider directory** under `integrations/providers/`:

```
integrations/providers/your_tool/
├── client.py    # Implements the relevant abstract base class
└── models.py    # Tool-specific data models
```

2. **Implement the abstract interface**:

```python
# integrations/providers/your_tool/client.py
from integrations.base import MonitoringProvider

class YourToolClient(MonitoringProvider):
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self._client = httpx.AsyncClient(...)

    async def get_current_alerts(self, filters: dict) -> list[Alert]:
        response = await self._client.get("/api/alerts", params=filters)
        return [Alert.from_api(a) for a in response.json()]
    ...
```

3. **Register in the integration registry**:

```python
# integrations/registry.py
PROVIDER_MAP = {
    "monitoring": {
        "mock": MockDatadog,
        "datadog": DatadogClient,
        "your_tool": YourToolClient,  # ← add here
    }
}
```

4. **Add configuration**:

```env
# .env
YOUR_TOOL_MODE=live
YOUR_TOOL_API_KEY=your-key-here
YOUR_TOOL_BASE_URL=https://api.yourtool.com
```

## Configuration Reference

### Environment Variables

```env
# Global mode: "mock" or "live"
RUNBOOK_MODE=mock

# Per-integration overrides (override global mode)
SERVICENOW_MODE=live
SERVICENOW_INSTANCE=mycompany.service-now.com
SERVICENOW_USERNAME=admin
SERVICENOW_PASSWORD=secret

DATADOG_MODE=mock
DATADOG_API_KEY=
DATADOG_APP_KEY=

PAGERDUTY_MODE=mock
PAGERDUTY_API_KEY=

AWS_MODE=mock
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1

SLACK_MODE=mock
SLACK_BOT_TOKEN=

# ML Engine
ML_ENGINE_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key-here
ML_MODEL=claude-sonnet-4-5-20250929
```
