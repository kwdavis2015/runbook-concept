# Contributing

## Development Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy environment template
cp .env.example .env

# Run in mock mode
streamlit run app/main.py
```

## Code Conventions

- **Python 3.11+** with type hints everywhere
- **Pydantic v2** for all data models
- **async/await** for all integration calls
- **Black** for formatting, **ruff** for linting
- Docstrings on all public classes and methods
- Integration providers must implement the abstract base class fully

## Adding a New Mock Scenario

1. Create a JSON file in `integrations/mock/fixtures/scenarios/`
2. Follow the schema established by existing scenarios (provide data for all integration types)
3. Register the scenario key in the mock configuration
4. Test: switch to the new scenario in the UI and verify the diagnostic flow

## Adding a New Real Integration

See [INTEGRATIONS.md](INTEGRATIONS.md) for the step-by-step guide.

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov=core --cov=ml --cov=integrations

# Run specific test module
pytest tests/unit/test_orchestrator.py
```
