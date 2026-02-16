"""Shared base class and utilities for all mock providers."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from app.config import Settings

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SCENARIOS_DIR = FIXTURES_DIR / "scenarios"

MOCK_DELAYS: dict[str, float] = {
    "servicenow": 0.5,
    "datadog": 0.3,
    "pagerduty": 0.2,
    "aws": 0.4,
    "slack": 0.1,
}


class MockBase:
    """Base class for mock providers.

    Handles scenario fixture loading and optional artificial latency.
    """

    provider_key: str = ""  # Override in subclasses (e.g. "servicenow", "datadog")

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._scenario_data: dict[str, Any] = {}
        self._load_scenario()

    def _load_scenario(self) -> None:
        """Load the active scenario fixture from disk."""
        scenario_name = self._settings.mock_scenario
        scenario_path = SCENARIOS_DIR / f"{scenario_name}.json"

        if not scenario_path.exists():
            self._scenario_data = {}
            return

        with open(scenario_path) as f:
            full_scenario = json.load(f)

        # Each provider reads its own section from the scenario file
        self._scenario_data = full_scenario.get(self.provider_key, {})

    def reload_scenario(self) -> None:
        """Re-read the scenario file (e.g. after the user switches scenarios)."""
        self._load_scenario()

    async def _simulate_delay(self) -> None:
        """Sleep to simulate real API latency, if delay is enabled."""
        if self._settings.mock_delay_enabled:
            delay = MOCK_DELAYS.get(self.provider_key, 0.2)
            await asyncio.sleep(delay)

    def _get(self, key: str, default: Any = None) -> Any:
        """Convenience accessor for scenario data."""
        return self._scenario_data.get(key, default)
