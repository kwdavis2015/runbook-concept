.PHONY: venv run run-live install install-dev test test-cov lint format clean

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

venv:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip

run:
	$(VENV)/bin/streamlit run app/main.py

run-live:
	RUNBOOK_MODE=live $(VENV)/bin/streamlit run app/main.py

install: venv
	$(PIP) install -e .

install-dev: venv
	$(PIP) install -e ".[dev]"

test:
	$(VENV)/bin/pytest

test-cov:
	$(VENV)/bin/pytest --cov=app --cov=core --cov=ml --cov=integrations

lint:
	$(VENV)/bin/ruff check .

format:
	$(VENV)/bin/black .
	$(VENV)/bin/ruff check --fix .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov
