"""ML engine interface — abstract base and Anthropic implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import (
        Classification,
        DiagnosticResult,
        Finding,
        Incident,
        RecommendationSet,
    )


class MLEngine(ABC):
    """Abstract interface for the ML engine.

    All capabilities accept structured data and return typed Pydantic models.
    Implementations may call an LLM or return canned responses (mock).
    """

    @abstractmethod
    async def classify(self, problem_description: str) -> Classification:
        """Classify a problem description into category + severity."""
        ...

    @abstractmethod
    async def diagnose(
        self,
        problem_description: str,
        findings: list[Finding],
    ) -> DiagnosticResult:
        """Analyze gathered evidence and determine root cause."""
        ...

    @abstractmethod
    async def recommend(
        self,
        problem_description: str,
        diagnosis: DiagnosticResult,
        findings: list[Finding],
    ) -> RecommendationSet:
        """Produce ranked action recommendations based on diagnosis."""
        ...

    @abstractmethod
    async def summarize(self, incident: Incident) -> str:
        """Generate a human-readable narrative summary of an incident."""
        ...


class AnthropicEngine(MLEngine):
    """ML engine backed by the Anthropic Claude API."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929") -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def _call(self, system: str, user: str, max_tokens: int = 2048) -> str:
        """Send a prompt to the Anthropic API and return the text response."""
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text

    async def classify(self, problem_description: str) -> Classification:
        from ml.prompts.diagnosis import build_classification_prompt
        from ml.classifier import parse_classification

        system, user = build_classification_prompt(problem_description)
        raw = await self._call(system, user, max_tokens=1024)
        return parse_classification(raw)

    async def diagnose(
        self,
        problem_description: str,
        findings: list[Finding],
    ) -> DiagnosticResult:
        from ml.prompts.diagnosis import build_diagnosis_prompt
        from ml.classifier import parse_diagnostic_result

        system, user = build_diagnosis_prompt(problem_description, findings)
        raw = await self._call(system, user, max_tokens=2048)
        return parse_diagnostic_result(raw)

    async def recommend(
        self,
        problem_description: str,
        diagnosis: DiagnosticResult,
        findings: list[Finding],
    ) -> RecommendationSet:
        from ml.prompts.resolution import build_resolution_prompt
        from ml.recommender import parse_recommendation_set

        system, user = build_resolution_prompt(problem_description, diagnosis, findings)
        raw = await self._call(system, user, max_tokens=2048)
        return parse_recommendation_set(raw)

    async def summarize(self, incident: Incident) -> str:
        from ml.prompts.summarization import build_summarization_prompt

        system, user = build_summarization_prompt(incident)
        raw = await self._call(system, user, max_tokens=2048)
        return raw.strip()
