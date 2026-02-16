"""Action recommendation parsing."""

from __future__ import annotations

import json
import logging

from core.models import (
    ActionRecommendation,
    RecommendationSet,
    RiskLevel,
)

logger = logging.getLogger(__name__)


def _extract_json(raw: str) -> dict:
    """Extract a JSON object from an LLM response that may contain markdown fencing."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def parse_recommendation_set(raw: str) -> RecommendationSet:
    """Parse an LLM response into a RecommendationSet model."""
    try:
        data = _extract_json(raw)
        recommendations = []
        for rec in data.get("recommendations", []):
            recommendations.append(
                ActionRecommendation(
                    description=rec.get("description", ""),
                    risk_level=RiskLevel(rec.get("risk_level", "low")),
                    requires_approval=rec.get("requires_approval", False),
                    integration=rec.get("integration"),
                    method=rec.get("method"),
                    params=rec.get("params", {}),
                    reasoning=rec.get("reasoning", ""),
                )
            )
        return RecommendationSet(
            recommendations=recommendations,
            summary=data.get("summary", ""),
            requires_immediate_action=data.get("requires_immediate_action", False),
        )
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning("Failed to parse recommendation response: %s", e)
        return RecommendationSet(
            summary=f"Parse error: {e}. Raw response: {raw[:200]}",
        )
