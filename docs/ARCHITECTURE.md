# Architecture & Design

## System Overview

Runbook Concept follows a layered architecture with clear separation between the UI, business logic, ML engine, and external integrations. The integration layer uses a provider pattern that makes it trivial to swap mock services for real ones.

## Directory Structure

```
runbook-concept/
├── app/
│   ├── main.py                    # Streamlit entrypoint
│   ├── config.py                  # App configuration & environment
│   ├── pages/
│   │   ├── chat.py                # Conversational troubleshooting interface
│   │   ├── dashboard.py           # Active incidents & metrics
│   │   ├── runbooks.py            # Browse/manage runbook library
│   │   ├── incident_detail.py     # Single incident deep-dive
│   │   └── settings.py            # Integration config & preferences
│   ├── components/
│   │   ├── incident_timeline.py   # Visual timeline of diagnostic steps
│   │   ├── approval_gate.py       # Human approval UI for critical actions
│   │   ├── context_panel.py       # Side panel showing gathered evidence
│   │   └── metric_cards.py        # Dashboard metric widgets
│   └── state/
│       └── session.py             # Streamlit session state management
│
├── core/
│   ├── orchestrator.py            # Main workflow engine
│   ├── models.py                  # Pydantic models (Incident, Action, Finding, etc.)
│   ├── runbook_engine.py          # Runbook parsing, step execution
│   └── exceptions.py              # Custom exceptions
│
├── ml/
│   ├── engine.py                  # ML engine interface
│   ├── classifier.py              # Problem classification / intent detection
│   ├── recommender.py             # Action recommendation
│   ├── summarizer.py              # Incident summarization
│   └── prompts/
│       ├── diagnosis.py           # Prompt templates for diagnosis
│       ├── resolution.py          # Prompt templates for resolution steps
│       └── summarization.py       # Prompt templates for summaries
│
├── integrations/
│   ├── base.py                    # Abstract base classes for all integrations
│   ├── registry.py                # Integration registry & factory
│   ├── providers/
│   │   ├── servicenow/
│   │   │   ├── client.py          # Real ServiceNow API client
│   │   │   └── models.py          # ServiceNow-specific models
│   │   ├── pagerduty/
│   │   │   ├── client.py          # Real PagerDuty API client
│   │   │   └── models.py
│   │   ├── datadog/
│   │   │   ├── client.py          # Real Datadog API client
│   │   │   └── models.py
│   │   ├── aws/
│   │   │   ├── client.py          # Real AWS client (CloudWatch, EC2, etc.)
│   │   │   └── models.py
│   │   ├── jira/
│   │   │   ├── client.py
│   │   │   └── models.py
│   │   └── slack/
│   │       ├── client.py
│   │       └── models.py
│   └── mock/
│       ├── mock_servicenow.py     # Mock ServiceNow with canned responses
│       ├── mock_pagerduty.py      # Mock PagerDuty
│       ├── mock_datadog.py        # Mock Datadog metrics & alerts
│       ├── mock_aws.py            # Mock AWS resources & logs
│       ├── mock_jira.py           # Mock Jira
│       ├── mock_slack.py          # Mock Slack
│       └── fixtures/
│           ├── incidents.json     # Sample incident data
│           ├── metrics.json       # Sample metric time series
│           ├── alerts.json        # Sample alerts
│           ├── logs.json          # Sample log entries
│           ├── resources.json     # Sample infrastructure inventory
│           └── scenarios/
│               ├── high_cpu.json           # Complete scenario: high CPU on prod server
│               ├── database_connection.json # Complete scenario: DB connection exhaustion
│               ├── deployment_failure.json  # Complete scenario: failed deployment
│               └── network_latency.json     # Complete scenario: cross-region latency
│
├── runbooks/
│   ├── high_cpu_troubleshooting.yaml
│   ├── database_connectivity.yaml
│   ├── deployment_rollback.yaml
│   ├── disk_space_remediation.yaml
│   └── network_troubleshooting.yaml
│
├── tests/
│   ├── unit/
│   │   ├── test_orchestrator.py
│   │   ├── test_ml_engine.py
│   │   ├── test_runbook_engine.py
│   │   └── test_integrations.py
│   ├── integration/
│   │   └── test_end_to_end.py
│   └── conftest.py
│
├── docs/
│   ├── ARCHITECTURE.md            # This file
│   ├── INTEGRATIONS.md            # Integration guide
│   ├── MOCK_SERVICES.md           # Mock services documentation
│   ├── ROADMAP.md                 # Implementation plan & progress
│   └── CONTRIBUTING.md            # Contribution guidelines
│
├── .env.example                   # Template for environment variables
├── requirements.txt
├── pyproject.toml
└── Makefile                       # Common development commands
```

## Core Concepts

### Incident Lifecycle

```
Problem Reported → Triage → Diagnosis → Recommendation → Approval → Execution → Verification → Resolution
       │              │          │              │              │           │             │            │
    User input    Classify    Gather        Suggest        Human      Execute       Confirm       Close
                  severity    evidence      actions        gate       action        fix           incident
```

### The Orchestrator

The `Orchestrator` is the central coordinator. When a user describes a problem:

1. **Classify** — ML engine categorizes the problem (network, compute, database, deployment, etc.)
2. **Gather Context** — queries relevant integrations for current state (metrics, logs, alerts, recent changes)
3. **Diagnose** — ML engine analyzes gathered context against known patterns and runbooks
4. **Recommend** — suggests one or more resolution actions, each tagged with a risk level
5. **Gate** — presents recommendations to the operator; critical/destructive actions require explicit approval
6. **Execute** — runs approved actions through the integration layer
7. **Verify** — re-queries integrations to confirm the problem is resolved
8. **Document** — generates an incident summary and timeline

### Provider Pattern (Mock ↔ Real Swap)

Every integration implements a shared abstract interface:

```python
# integrations/base.py
class MonitoringProvider(ABC):
    @abstractmethod
    async def get_current_alerts(self, filters: dict) -> list[Alert]: ...

    @abstractmethod
    async def get_metrics(self, query: MetricQuery) -> MetricTimeSeries: ...

    @abstractmethod
    async def get_logs(self, query: LogQuery) -> list[LogEntry]: ...
```

The `IntegrationRegistry` resolves which provider to use based on configuration:

```python
# Controlled by RUNBOOK_MODE env var or per-integration overrides
registry = IntegrationRegistry(mode="mock")  # or "live"
monitoring = registry.get_provider("monitoring")  # returns MockDatadog or Datadog
```

To switch a single integration from mock to real:

```env
RUNBOOK_MODE=mock                    # default everything to mock
SERVICENOW_MODE=live                 # override: use real ServiceNow
SERVICENOW_INSTANCE=mycompany.service-now.com
SERVICENOW_USERNAME=api_user
SERVICENOW_PASSWORD=secret
```

### ML Engine

The ML engine is designed to be model-agnostic. It wraps an LLM (defaulting to Anthropic's Claude) and provides structured interfaces for each capability:

- **Classifier** — given a problem description, returns a category + severity + confidence score
- **Recommender** — given gathered context + runbook steps, returns ranked action recommendations
- **Summarizer** — given an incident timeline, produces a human-readable summary

The engine uses structured prompts with the gathered integration data injected as context, enabling the LLM to reason over real (or mocked) operational data.

### Runbook Format

Runbooks are defined in YAML with conditional logic:

```yaml
name: High CPU Troubleshooting
trigger: cpu_usage > 90%
severity: high
steps:
  - id: identify_process
    action: gather
    description: "Identify top CPU-consuming processes"
    integration: compute
    method: get_top_processes
    params:
      host: "{{ incident.host }}"
      limit: 10

  - id: check_recent_deploys
    action: gather
    description: "Check for recent deployments"
    integration: ticketing
    method: get_recent_changes
    params:
      timeframe: "2h"

  - id: decide_action
    action: ml_decision
    description: "Determine root cause and recommended action"
    context:
      - identify_process
      - check_recent_deploys

  - id: restart_service
    action: execute
    description: "Restart the problematic service"
    requires_approval: true
    risk_level: medium
    integration: compute
    method: restart_service
    params:
      host: "{{ incident.host }}"
      service: "{{ decide_action.target_service }}"
```

### Human Approval Gates

Actions are tagged with risk levels. The approval policy is configurable:

| Risk Level | Default Policy |
|-----------|----------------|
| `low` | Auto-execute (e.g., gather logs, query metrics) |
| `medium` | Notify + execute unless vetoed within timeout |
| `high` | Require explicit operator approval |
| `critical` | Require approval from 2 operators |

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit |
| Backend | Python 3.11+ |
| ML Engine | Anthropic Claude API (pluggable) |
| Data Models | Pydantic v2 |
| Async | asyncio + httpx |
| Testing | pytest + pytest-asyncio |
| Configuration | pydantic-settings + .env |
