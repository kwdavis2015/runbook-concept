"""Prompt templates for incident summarization."""

from __future__ import annotations

from core.models import Incident

SUMMARIZATION_SYSTEM = """\
You are an expert IT operations analyst writing an incident summary. \
You will be given the full details of a resolved (or in-progress) incident \
including its timeline, findings, and actions taken.

Write a clear, concise incident summary suitable for a post-incident review. \
Include:
1. What happened (the problem)
2. Root cause
3. Key evidence that led to the diagnosis
4. Actions taken to resolve
5. Current status

Write in plain prose, 3-5 paragraphs. Be factual and concise.
"""


def build_summarization_prompt(incident: Incident) -> tuple[str, str]:
    """Return (system, user) messages for the summarization prompt."""
    lines = [
        f"INCIDENT: {incident.id} — {incident.title}",
        f"Status: {incident.status}",
        f"Severity: {incident.severity}",
        f"Category: {incident.category}",
    ]

    if incident.classification:
        lines.append(f"Classification: {incident.classification.category} "
                      f"(confidence: {incident.classification.confidence:.0%})")
        if incident.classification.reasoning:
            lines.append(f"  Reasoning: {incident.classification.reasoning}")

    if incident.timeline:
        lines.append("\nTIMELINE:")
        for entry in incident.timeline:
            lines.append(f"  {entry.timestamp} [{entry.event_type}] {entry.summary}")

    if incident.findings:
        lines.append("\nFINDINGS:")
        for f in incident.findings:
            lines.append(f"  - [{f.finding_type}] {f.summary} (source: {f.source})")

    if incident.actions:
        lines.append("\nACTIONS:")
        for a in incident.actions:
            status = "executed" if a.executed_at else ("approved" if a.approved else "pending")
            lines.append(f"  - {a.description} — {status} (risk: {a.risk_level})")
            if a.error:
                lines.append(f"    ERROR: {a.error}")

    user = "\n".join(lines) + "\n\nWrite the incident summary."
    return SUMMARIZATION_SYSTEM, user
