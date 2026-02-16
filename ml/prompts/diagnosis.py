"""Prompt templates for problem classification and root cause diagnosis."""

from __future__ import annotations

from core.models import Finding
from ml.prompts.context import build_context_block, format_findings

# ---------------------------------------------------------------------------
# Classification prompt
# ---------------------------------------------------------------------------

CLASSIFICATION_SYSTEM = """\
You are an expert IT operations analyst. Your job is to classify incoming \
problem reports into a category and severity level.

Respond ONLY with valid JSON in this exact format:
{
  "category": "<one of: compute, network, database, deployment, storage, security, application, unknown>",
  "severity": "<one of: low, medium, high, critical>",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<one sentence explaining your classification>"
}
"""


def build_classification_prompt(problem_description: str) -> tuple[str, str]:
    """Return (system, user) messages for the classification prompt."""
    user = f"Classify the following problem report:\n\n{problem_description}"
    return CLASSIFICATION_SYSTEM, user


# ---------------------------------------------------------------------------
# Diagnosis prompt
# ---------------------------------------------------------------------------

DIAGNOSIS_SYSTEM = """\
You are an expert IT operations analyst performing root cause analysis. \
You will be given a problem description and operational evidence gathered \
from monitoring, ticketing, and infrastructure systems.

Analyze the evidence and determine the most likely root cause.

Respond ONLY with valid JSON in this exact format:
{
  "root_cause": "<concise description of the root cause>",
  "evidence_summary": "<summary of the key evidence that supports your conclusion>",
  "confidence": <float between 0.0 and 1.0>,
  "contributing_factors": ["<factor 1>", "<factor 2>", ...],
  "affected_components": ["<component 1>", "<component 2>", ...]
}
"""


def build_diagnosis_prompt(
    problem_description: str,
    findings: list[Finding],
) -> tuple[str, str]:
    """Return (system, user) messages for the diagnosis prompt."""
    context = format_findings(findings)
    user = (
        f"PROBLEM:\n{problem_description}\n\n"
        f"{context}\n\n"
        "Based on the evidence above, determine the root cause."
    )
    return DIAGNOSIS_SYSTEM, user
