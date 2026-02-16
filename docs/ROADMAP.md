# Roadmap & Progress

## Implementation Phases

### Phase 1: Foundation ✅
> Core project structure, data models, and basic Streamlit shell

| Task | Status | Notes |
|------|--------|-------|
| Project scaffolding & dependency setup | ✅ Complete | pyproject.toml, requirements.txt, requirements-dev.txt, Makefile |
| Core data models (Pydantic) | ✅ Complete | Incident, Action, Finding, Alert, MetricTimeSeries + enums |
| Abstract integration base classes | ✅ Complete | TicketingProvider, MonitoringProvider, AlertingProvider, CommunicationProvider |
| Integration registry & factory | ✅ Complete | Mode-based provider resolution with lazy imports |
| Configuration system | ✅ Complete | pydantic-settings, .env loading, per-integration overrides |
| Basic Streamlit app shell | ✅ Complete | st.navigation multi-page layout, session state, stub pages & components |
| Settings page | ✅ Complete | Toggle mock/live, select scenario, view integration status |

### Phase 2: Mock Services ⬜
> Complete mock layer with scenario-driven fixtures

| Task | Status | Notes |
|------|--------|-------|
| Mock ServiceNow provider | ⬜ Not started | Incidents, changes, knowledge base |
| Mock Datadog provider | ⬜ Not started | Alerts, metrics, logs |
| Mock PagerDuty provider | ⬜ Not started | Incidents, on-call |
| Mock AWS provider | ⬜ Not started | Instances, processes, CloudWatch |
| Mock Slack provider | ⬜ Not started | Messages, channels |
| Scenario: High CPU | ⬜ Not started | Full fixture data across all integrations |
| Scenario: Database Connection | ⬜ Not started | |
| Scenario: Deployment Failure | ⬜ Not started | |
| Scenario: Network Latency | ⬜ Not started | |
| Mock delay simulation | ⬜ Not started | Configurable artificial latency |

### Phase 3: ML Engine ⬜
> LLM-powered classification, diagnosis, and recommendation

| Task | Status | Notes |
|------|--------|-------|
| ML engine interface | ⬜ Not started | Abstract base + Anthropic implementation |
| Problem classifier | ⬜ Not started | Category + severity from natural language |
| Diagnostic analyzer | ⬜ Not started | Reason over gathered context |
| Action recommender | ⬜ Not started | Ranked suggestions with risk levels |
| Incident summarizer | ⬜ Not started | Timeline → narrative summary |
| Prompt templates | ⬜ Not started | Diagnosis, resolution, summarization |
| Mock ML engine (no API key needed) | ⬜ Not started | Canned responses for demo mode |

### Phase 4: Orchestrator ⬜
> Workflow engine connecting ML, integrations, and human approval

| Task | Status | Notes |
|------|--------|-------|
| Orchestrator core loop | ⬜ Not started | Classify → gather → diagnose → recommend → execute |
| Runbook YAML parser | ⬜ Not started | Load and validate runbook definitions |
| Runbook step executor | ⬜ Not started | Execute gather/action steps via integrations |
| Human approval gate logic | ⬜ Not started | Risk-level-based approval policies |
| Incident timeline tracking | ⬜ Not started | Record every step, finding, and action |
| Verification loop | ⬜ Not started | Re-query after action to confirm resolution |

### Phase 5: UI / UX ⬜
> Full Streamlit interface for conversational troubleshooting

| Task | Status | Notes |
|------|--------|-------|
| Chat interface | ⬜ Not started | Natural language problem intake |
| Incident dashboard | ⬜ Not started | Active incidents, metrics overview |
| Incident detail view | ⬜ Not started | Timeline, context, actions taken |
| Approval gate UI | ⬜ Not started | Inline approval buttons with risk context |
| Context panel | ⬜ Not started | Side panel showing gathered evidence |
| Runbook library browser | ⬜ Not started | Browse, view, select runbooks |
| Scenario selector | ⬜ Not started | Easy mock scenario switching in UI |

### Phase 6: Real Integrations ⬜
> Swap out mocks for production API clients

| Task | Status | Notes |
|------|--------|-------|
| ServiceNow real client | ⬜ Not started | REST API integration |
| Datadog real client | ⬜ Not started | Metrics, logs, alerts APIs |
| PagerDuty real client | ⬜ Not started | Events & incidents API |
| AWS real client | ⬜ Not started | boto3 — EC2, CloudWatch |
| Jira real client | ⬜ Not started | REST API v3 |
| Slack real client | ⬜ Not started | Bolt SDK |

### Phase 7: Polish & Testing ⬜
> Production readiness

| Task | Status | Notes |
|------|--------|-------|
| Unit tests — core models | ⬜ Not started | |
| Unit tests — orchestrator | ⬜ Not started | |
| Unit tests — ML engine | ⬜ Not started | |
| Unit tests — integrations | ⬜ Not started | |
| End-to-end test with mocks | ⬜ Not started | Full scenario walkthrough |
| Error handling & edge cases | ⬜ Not started | |
| Loading states & UX polish | ⬜ Not started | |
| README & documentation review | ⬜ Not started | |

## Legend

| Icon | Meaning |
|------|---------|
| ⬜ | Not started |
| 🟡 | In progress |
| ✅ | Complete |
| ❌ | Blocked / deferred |

## Priority Order

Phases 1–5 are the **demo-ready** path — everything needed to show a hiring manager the concept working end-to-end with mocks. Phase 6 (real integrations) is optional for the initial demo. Phase 7 ensures quality before sharing widely.

Recommended build order within the demo-ready path:

1. **Phase 1** — get the skeleton running
2. **Phase 2** — populate mocks (the app needs data to be interesting)
3. **Phase 3** — wire up the ML engine (the "brain")
4. **Phase 4** — build the orchestrator (connects everything)
5. **Phase 5** — make it look good
