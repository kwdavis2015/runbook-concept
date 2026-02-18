# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env

# Run (mock mode — no external services needed)
make run

# Run with real integrations
make run-live          # sets RUNBOOK_MODE=live

# Tests
make test
make test-cov          # with coverage report
pytest tests/unit/test_orchestrator.py   # single module

# Lint / format
make lint              # ruff
make format            # black + ruff --fix
```

## Architecture

The app is a Streamlit UI over a layered backend: **UI → Orchestrator → ML Engine + Integration Registry**.

### Orchestrator (`core/orchestrator.py`)

The central workflow engine. Full incident lifecycle:

```
create_incident → gather_context → diagnose → recommend → [approval gate] → execute_approved_actions → verify → summarize
```

`run_diagnosis()` is a convenience method that chains steps 1–4 and auto-approves low-risk actions. The `Orchestrator` is constructed with `Settings`, `IntegrationRegistry`, and `MLEngine` — all dependency-injected.

### Integration Registry (`integrations/registry.py`)

Resolves providers lazily by **category** (`ticketing`, `monitoring`, `alerting`, `compute`, `communication`). Mode is determined per-category: per-integration env var overrides (e.g. `SERVICENOW_MODE=live`) take precedence over global `RUNBOOK_MODE`. Providers are cached after first instantiation; call `registry.reset()` to force re-resolution.

To add a new real provider: implement the abstract base class in `integrations/base.py`, add the entry to `PROVIDER_MAP` in `registry.py`.

### ML Engine (`ml/engine.py`)

Abstract `MLEngine` with two concrete implementations:
- **`AnthropicEngine`** — calls Claude API; requires `ANTHROPIC_API_KEY`
- **`MockMLEngine`** — scenario-aware canned responses, no API key needed

Four operations: `classify()`, `diagnose()`, `recommend()`, `summarize()`. All return structured Pydantic models. Prompt templates live in `ml/prompts/`.

### Mock Layer (`integrations/mock/`)

Five mock providers (ServiceNow, Datadog, PagerDuty, AWS, Slack) all inherit from a shared `MockBase` that loads JSON fixtures. Scenario is set via `MOCK_SCENARIO` env var (options: `high_cpu`, `database_connection`, `deployment_failure`, `network_latency`). Scenario JSON files are in `integrations/mock/fixtures/scenarios/` and provide data for all integration types simultaneously.

### Configuration (`app/config.py`)

`Settings` via `pydantic-settings`. Loads `.env` automatically. `settings.get_integration_mode(integration)` returns the effective mode for a given integration name, checking the per-integration override before falling back to `runbook_mode`.

## Key Conventions

- Python 3.11+, type hints everywhere, Pydantic v2 models for all data structures
- All integration provider calls are `async` — the orchestrator is fully async
- `core/models.py` is the shared data contract — `Incident`, `Action`, `Finding`, `Alert`, `RiskLevel`, `Severity`, etc.
- New integration providers must fully implement the abstract base class in `integrations/base.py`
- New mock scenarios need a JSON file in `integrations/mock/fixtures/scenarios/` covering all integration categories

## Current Status

Phases 1–3 complete (foundation, mock services, ML engine). Phase 4 (orchestrator) is partially complete — the core loop exists in `core/orchestrator.py` but runbook YAML execution, the formal human approval gate, and verification loop are not yet wired into the UI. Phase 5 (UI) and Phase 6 (real integrations) are not started. See `docs/ROADMAP.md` for details.
