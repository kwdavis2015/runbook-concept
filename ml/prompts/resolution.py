"""Prompt templates for action recommendation and resolution planning."""

from __future__ import annotations

from core.models import DiagnosticResult, Finding
from ml.prompts.context import format_findings

RESOLUTION_SYSTEM = """\
You are an expert IT operations analyst recommending remediation actions. \
You will be given a problem description, a root cause diagnosis, and \
supporting evidence.

Recommend a ranked list of actions to resolve the issue. For each action, \
specify the risk level and whether human approval is required before execution.

Available integrations and methods:
- compute: restart_service, scale_instances
- ticketing: create_incident, update_incident
- communication: send_message, create_channel
- monitoring: silence_alert

Respond ONLY with valid JSON in this exact format:
{
  "summary": "<one sentence summary of the resolution plan>",
  "requires_immediate_action": <true or false>,
  "recommendations": [
    {
      "description": "<what to do>",
      "risk_level": "<one of: low, medium, high, critical>",
      "requires_approval": <true or false>,
      "integration": "<integration category or null>",
      "method": "<method name or null>",
      "params": { "<key>": "<value>", ... },
      "reasoning": "<why this action>"
    }
  ]
}

Order recommendations from most to least important. Tag destructive or \
state-changing actions as requiring approval.
"""


def build_resolution_prompt(
    problem_description: str,
    diagnosis: DiagnosticResult,
    findings: list[Finding],
) -> tuple[str, str]:
    """Return (system, user) messages for the resolution prompt."""
    evidence = format_findings(findings)
    user = (
        f"PROBLEM:\n{problem_description}\n\n"
        f"ROOT CAUSE DIAGNOSIS:\n"
        f"  Root cause: {diagnosis.root_cause}\n"
        f"  Evidence: {diagnosis.evidence_summary}\n"
        f"  Confidence: {diagnosis.confidence:.0%}\n"
        f"  Contributing factors: {', '.join(diagnosis.contributing_factors) or 'None identified'}\n"
        f"  Affected components: {', '.join(diagnosis.affected_components) or 'None identified'}\n\n"
        f"{evidence}\n\n"
        "Recommend actions to resolve this issue."
    )
    return RESOLUTION_SYSTEM, user
