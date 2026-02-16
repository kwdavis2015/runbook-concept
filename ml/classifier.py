"""Problem classification and diagnostic result parsing."""

from __future__ import annotations

import json
import logging

from core.models import (
    Classification,
    DiagnosticResult,
    ProblemCategory,
    Severity,
)

logger = logging.getLogger(__name__)


def _extract_json(raw: str) -> dict:
    """Extract a JSON object from an LLM response that may contain markdown fencing."""
    text = raw.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def parse_classification(raw: str) -> Classification:
    """Parse an LLM response into a Classification model."""
    try:
        data = _extract_json(raw)
        return Classification(
            category=ProblemCategory(data.get("category", "unknown")),
            severity=Severity(data.get("severity", "medium")),
            confidence=float(data.get("confidence", 0.0)),
            reasoning=data.get("reasoning", ""),
        )
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning("Failed to parse classification response: %s", e)
        return Classification(
            category=ProblemCategory.UNKNOWN,
            severity=Severity.MEDIUM,
            confidence=0.0,
            reasoning=f"Parse error: {e}. Raw response: {raw[:200]}",
        )


def parse_diagnostic_result(raw: str) -> DiagnosticResult:
    """Parse an LLM response into a DiagnosticResult model."""
    try:
        data = _extract_json(raw)
        return DiagnosticResult(
            root_cause=data.get("root_cause", "Unknown"),
            evidence_summary=data.get("evidence_summary", ""),
            confidence=float(data.get("confidence", 0.0)),
            contributing_factors=data.get("contributing_factors", []),
            affected_components=data.get("affected_components", []),
        )
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning("Failed to parse diagnostic result: %s", e)
        return DiagnosticResult(
            root_cause=f"Parse error — raw response available",
            evidence_summary=raw[:500],
            confidence=0.0,
        )
