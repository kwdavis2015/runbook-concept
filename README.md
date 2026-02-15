# Runbook Concept

An intelligent runbook application for diagnosing, troubleshooting, and resolving technology problems. Built with Python and Streamlit, powered by an ML engine, and designed for seamless human-in-the-loop interaction.

## Vision

Traditional runbooks are static documents that operators follow step-by-step. **Runbook Concept** transforms this into a dynamic, intelligent experience:

- **Conversational interface** — operators describe problems in natural language
- **Automated diagnostics** — the ML engine queries integrated tools and data sources to gather context
- **Guided resolution** — the system recommends actions, requests human approval for critical steps, and executes approved remediations
- **Learning loop** — resolved incidents feed back into the knowledge base

## Key Features

| Feature | Description |
|---------|-------------|
| 🧠 ML-Powered Diagnosis | Natural language problem intake → automated root cause analysis |
| 🔌 Integration Hub | Pluggable connectors for ServiceNow, PagerDuty, Datadog, AWS, etc. |
| 👤 Human-in-the-Loop | Approval gates for destructive/critical actions |
| 🧪 Mock Mode | Full set of mock services for demo and evaluation — no real infra needed |
| 📚 Runbook Library | Curated troubleshooting procedures the ML engine can reference and execute |
| 📊 Incident Timeline | Visual timeline of diagnostic steps, findings, and actions taken |

## Quick Start

```bash
# Clone and install
git clone <repo-url>
cd runbook-concept
pip install -r requirements.txt

# Run in mock mode (default) — no external services needed
streamlit run app/main.py

# Run with real integrations
cp .env.example .env
# Edit .env with your credentials
RUNBOOK_MODE=live streamlit run app/main.py
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Streamlit UI                       │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Chat     │  │ Incident     │  │ Runbook       │  │
│  │ Interface│  │ Dashboard    │  │ Library       │  │
│  └────┬─────┘  └──────┬───────┘  └───────┬───────┘  │
│       └───────────────┼───────────────────┘          │
│                       ▼                              │
│              ┌────────────────┐                      │
│              │  Orchestrator  │                      │
│              └───────┬────────┘                      │
│       ┌──────────────┼──────────────┐                │
│       ▼              ▼              ▼                │
│  ┌─────────┐  ┌───────────┐  ┌──────────┐           │
│  │ ML      │  │ Integration│  │ Action   │           │
│  │ Engine  │  │ Hub        │  │ Executor │           │
│  └─────────┘  └─────┬─────┘  └──────────┘           │
│                      │                               │
│         ┌────────────┼────────────┐                  │
│         ▼            ▼            ▼                  │
│    ┌─────────┐ ┌──────────┐ ┌─────────┐             │
│    │ Mock /  │ │ Mock /   │ │ Mock /  │             │
│    │ ServiceNow│ │ Datadog │ │ AWS    │             │
│    └─────────┘ └──────────┘ └─────────┘             │
└─────────────────────────────────────────────────────┘
```

## Project Status

See [docs/ROADMAP.md](docs/ROADMAP.md) for the full implementation plan and progress tracking.

## Documentation

- [Architecture & Design](docs/ARCHITECTURE.md)
- [Integration Guide](docs/INTEGRATIONS.md)
- [Mock Services](docs/MOCK_SERVICES.md)
- [Roadmap & Progress](docs/ROADMAP.md)
- [Contributing](docs/CONTRIBUTING.md)
