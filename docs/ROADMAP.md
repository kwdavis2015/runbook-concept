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

### Phase 2: Mock Services ✅
> Complete mock layer with scenario-driven fixtures

| Task | Status | Notes |
|------|--------|-------|
| Mock base class & scenario loader | ✅ Complete | Shared MockBase with JSON fixture loading and configurable delays |
| Mock ServiceNow provider | ✅ Complete | Incidents, changes, knowledge base |
| Mock Datadog provider | ✅ Complete | Alerts, metrics, logs, host info |
| Mock PagerDuty provider | ✅ Complete | Incidents, on-call, acknowledgement |
| Mock AWS provider | ✅ Complete | Instances, processes, service restart |
| Mock Slack provider | ✅ Complete | Messages, channels, session-persistent sent messages |
| Scenario: High CPU | ✅ Complete | Memory leak after deploy on prod-web-03 |
| Scenario: Database Connection | ✅ Complete | Connection pool exhaustion on db-primary-01 |
| Scenario: Deployment Failure | ✅ Complete | checkout-service v3.1.0 partial rollout failure |
| Scenario: Network Latency | ✅ Complete | EU latency from CDN misconfiguration |
| Mock delay simulation | ✅ Complete | Per-provider delays, toggled via MOCK_DELAY_ENABLED |
| Unit tests — models, config, mocks, registry | ✅ Complete | 58 tests covering Phase 1 & 2 deliverables (early Phase 7 work) |

### Phase 3: ML Engine ✅
> LLM-powered classification, diagnosis, and recommendation

| Task | Status | Notes |
|------|--------|-------|
| ML response models | ✅ Complete | DiagnosticResult, ActionRecommendation, RecommendationSet in core/models.py |
| ML engine interface | ✅ Complete | MLEngine ABC + AnthropicEngine concrete implementation |
| Prompt context builder | ✅ Complete | ml/prompts/context.py — formats integration data for prompt injection |
| Problem classifier | ✅ Complete | JSON parsing with graceful fallback on parse errors |
| Diagnostic analyzer | ✅ Complete | Root cause analysis with confidence scoring |
| Action recommender | ✅ Complete | Ranked suggestions with risk levels and integration targets |
| Incident summarizer | ✅ Complete | Timeline → narrative prose summary |
| Prompt templates | ✅ Complete | Diagnosis, resolution, summarization — structured JSON output prompts |
| Mock ML engine (no API key needed) | ✅ Complete | Scenario-aware canned responses for all 4 scenarios with fallback defaults |

### Phase 4: Orchestrator ✅
> Workflow engine connecting ML, integrations, and human approval

| Task | Status | Notes |
|------|--------|-------|
| Orchestrator core loop | ✅ Complete | Full lifecycle: create → classify → gather → diagnose → recommend → gate → execute → verify → summarize. Includes `run_diagnosis()` and `run_full_workflow()` convenience methods. |
| Runbook YAML parser | ✅ Complete | `core/runbook_engine.py` — `Runbook`, `RunbookStep` models; `RunbookParser`; `resolve_params` template resolver; 5 runbook YAML files in `runbooks/`; 77 unit tests |
| Runbook step executor | ✅ Complete | `RunbookStepExecutor` in `core/runbook_engine.py` — `execute_step`, `execute_runbook`, `resume_runbook`; gather-failure recovery; approval gate pause/resume; `_coerce_to_dict`; nested template resolution; 52 new unit tests |
| Human approval gate logic | ✅ Complete | `core/approval.py` — `ApprovalPolicyType` (auto/require_one/require_two), `ApprovalPolicy` dataclass, `DEFAULT_POLICY`, `ApprovalEvaluator`; multi-approver support; integrated into `Orchestrator`; 41 unit tests |
| Incident timeline tracking | ✅ Complete | `RunbookStepExecutor._append_timeline` records every executed step; `Orchestrator._add_timeline` covers all lifecycle phases |
| Verification loop | ✅ Complete | `verify()` returns `VerificationResult`; `verify_with_retry(max_attempts, interval_seconds)` with exponential-backoff-ready retry; `VerificationResult` model in `core/models.py` |

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

### Phase 7: Polish & Testing 🟡
> Production readiness

| Task | Status | Notes |
|------|--------|-------|
| Unit tests — core models | ✅ Complete | 19 tests — enums, model creation, defaults, serialization (done early in Phase 2) |
| Unit tests — config | ✅ Complete | 9 tests — defaults, integration mode overrides (done early in Phase 2) |
| Unit tests — integrations (mocks + registry) | ✅ Complete | 30 tests — all 5 mock providers, scenario switching, registry resolution, caching (done early in Phase 2) |
| Unit tests — orchestrator | ✅ Complete | 36 tests — create, gather, diagnose, recommend, approval gate (single + multi-approver), execute, verify, verify_with_retry, run_diagnosis, run_full_workflow (done in Phase 4) |
| Unit tests — ML engine | ⬜ Not started | |
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
