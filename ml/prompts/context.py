"""Prompt context builder — formats integration data into structured text for LLM prompts."""

from __future__ import annotations

from core.models import (
    Alert,
    ChangeRecord,
    Finding,
    HostInfo,
    LogEntry,
    MetricTimeSeries,
    ProcessInfo,
)


def format_alerts(alerts: list[Alert]) -> str:
    if not alerts:
        return "No active alerts."
    lines = ["ACTIVE ALERTS:"]
    for a in alerts:
        line = f"  - [{a.severity.upper()}] {a.name}"
        if a.host:
            line += f" on {a.host}"
        if a.value is not None and a.threshold is not None:
            line += f" (value: {a.value}, threshold: {a.threshold})"
        if a.triggered_at:
            line += f" — triggered {a.triggered_at}"
        lines.append(line)
    return "\n".join(lines)


def format_metrics(series_list: list[MetricTimeSeries]) -> str:
    if not series_list:
        return "No metric data available."
    lines = ["METRICS:"]
    for ts in series_list:
        header = f"  {ts.metric_name}"
        if ts.host:
            header += f" ({ts.host})"
        lines.append(header)
        for p in ts.points[-10:]:  # last 10 points to keep context manageable
            lines.append(f"    {p.timestamp}: {p.value}")
    return "\n".join(lines)


def format_logs(logs: list[LogEntry]) -> str:
    if not logs:
        return "No log entries."
    lines = ["LOGS:"]
    for log in logs[-15:]:  # last 15 entries
        line = f"  [{log.level.upper()}] {log.timestamp}"
        if log.host:
            line += f" {log.host}"
        if log.service:
            line += f"/{log.service}"
        line += f": {log.message}"
        lines.append(line)
    return "\n".join(lines)


def format_changes(changes: list[ChangeRecord]) -> str:
    if not changes:
        return "No recent changes."
    lines = ["RECENT CHANGES:"]
    for c in changes:
        line = f"  - {c.number}: {c.description}"
        if c.created_at:
            line += f" (created: {c.created_at})"
        if c.requested_by:
            line += f" by {c.requested_by}"
        lines.append(line)
    return "\n".join(lines)


def format_host_info(host: HostInfo | None) -> str:
    if not host:
        return "No host information available."
    lines = [
        "HOST INFO:",
        f"  Hostname: {host.hostname}",
    ]
    if host.instance_id:
        lines.append(f"  Instance ID: {host.instance_id}")
    if host.instance_type:
        lines.append(f"  Instance type: {host.instance_type}")
    lines.append(f"  State: {host.state}")
    if host.ip_address:
        lines.append(f"  IP: {host.ip_address}")
    if host.region:
        lines.append(f"  Region: {host.region}")
    return "\n".join(lines)


def format_processes(processes: list[ProcessInfo]) -> str:
    if not processes:
        return "No process information available."
    lines = ["TOP PROCESSES:"]
    for p in processes:
        line = f"  PID {p.pid}: {p.name} — CPU {p.cpu_percent}%, MEM {p.memory_percent}%"
        if p.user:
            line += f" (user: {p.user})"
        if p.command:
            line += f"\n    cmd: {p.command}"
        lines.append(line)
    return "\n".join(lines)


def format_findings(findings: list[Finding]) -> str:
    """Format a list of findings into a structured context block."""
    if not findings:
        return "No evidence gathered yet."
    lines = ["GATHERED EVIDENCE:"]
    for i, f in enumerate(findings, 1):
        lines.append(f"  {i}. [{f.finding_type}] {f.summary} (source: {f.source}, confidence: {f.confidence:.0%})")
        if f.details:
            for k, v in f.details.items():
                lines.append(f"      {k}: {v}")
    return "\n".join(lines)


def build_context_block(
    *,
    alerts: list[Alert] | None = None,
    metrics: list[MetricTimeSeries] | None = None,
    logs: list[LogEntry] | None = None,
    changes: list[ChangeRecord] | None = None,
    host: HostInfo | None = None,
    processes: list[ProcessInfo] | None = None,
    findings: list[Finding] | None = None,
) -> str:
    """Build a complete context block from all available integration data.

    Returns a single formatted string ready for prompt injection.
    """
    sections = []

    if alerts:
        sections.append(format_alerts(alerts))
    if metrics:
        sections.append(format_metrics(metrics))
    if logs:
        sections.append(format_logs(logs))
    if changes:
        sections.append(format_changes(changes))
    if host:
        sections.append(format_host_info(host))
    if processes:
        sections.append(format_processes(processes))
    if findings:
        sections.append(format_findings(findings))

    if not sections:
        return "No operational context available."

    return "\n\n".join(sections)
