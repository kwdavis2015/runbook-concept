"""Runbook YAML parser, Pydantic models, template resolver, and step executor."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from core.exceptions import RunbookParseError
from core.models import (
    Finding,
    FindingType,
    Incident,
    ProblemCategory,
    RiskLevel,
    Severity,
    TimelineEntry,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — kept in sync with integrations/registry.py PROVIDER_MAP
# and integrations/base.py abstract methods.
# ---------------------------------------------------------------------------

VALID_INTEGRATIONS: frozenset[str] = frozenset(
    {"ticketing", "monitoring", "alerting", "compute", "communication"}
)

VALID_METHODS: dict[str, frozenset[str]] = {
    "ticketing": frozenset(
        {
            "get_incident",
            "create_incident",
            "update_incident",
            "get_recent_changes",
            "add_work_note",
            "search_knowledge_base",
        }
    ),
    "monitoring": frozenset(
        {
            "get_current_alerts",
            "get_metrics",
            "get_logs",
            "get_host_info",
            "get_top_processes",
        }
    ),
    "alerting": frozenset(
        {
            "get_active_incidents",
            "get_on_call",
            "trigger_alert",
            "acknowledge_alert",
        }
    ),
    "compute": frozenset(
        {
            "get_host_info",
            "get_top_processes",
            "restart_service",
        }
    ),
    "communication": frozenset(
        {
            "send_message",
            "create_channel",
            "get_recent_messages",
        }
    ),
}

VALID_ACTIONS: frozenset[str] = frozenset({"gather", "execute", "ml_decision"})

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class RunbookStep(BaseModel):
    """A single step in a runbook definition."""

    id: str
    action: str
    description: str
    integration: str | None = None
    method: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    # Step IDs whose results should be passed as context (ml_decision steps)
    context: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    # Reserved for future conditional execution logic
    condition: str | None = None

    @model_validator(mode="after")
    def _validate_step(self) -> RunbookStep:
        if self.action not in VALID_ACTIONS:
            raise ValueError(
                f"Step '{self.id}': invalid action '{self.action}'. "
                f"Must be one of: {sorted(VALID_ACTIONS)}"
            )

        if self.action in {"gather", "execute"}:
            if not self.integration:
                raise ValueError(
                    f"Step '{self.id}' (action={self.action}) requires 'integration'"
                )
            if not self.method:
                raise ValueError(
                    f"Step '{self.id}' (action={self.action}) requires 'method'"
                )
            if self.integration not in VALID_INTEGRATIONS:
                raise ValueError(
                    f"Step '{self.id}': unknown integration '{self.integration}'. "
                    f"Valid: {sorted(VALID_INTEGRATIONS)}"
                )
            valid_methods = VALID_METHODS.get(self.integration, frozenset())
            if self.method not in valid_methods:
                raise ValueError(
                    f"Step '{self.id}': unknown method '{self.method}' for "
                    f"integration '{self.integration}'. "
                    f"Valid: {sorted(valid_methods)}"
                )

        return self


class Runbook(BaseModel):
    """A fully validated runbook loaded from a YAML file."""

    name: str
    description: str = ""
    # Human-readable trigger condition (informational, not evaluated by the engine)
    trigger: str | None = None
    severity: Severity | None = None
    category: ProblemCategory | None = None
    tags: list[str] = Field(default_factory=list)
    steps: list[RunbookStep]
    # Set by the parser after loading; not part of the YAML schema
    source_path: str | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _validate_structure(self) -> Runbook:
        # Detect duplicate step IDs
        seen: set[str] = set()
        duplicates: set[str] = set()
        for step in self.steps:
            if step.id in seen:
                duplicates.add(step.id)
            seen.add(step.id)
        if duplicates:
            raise ValueError(f"Duplicate step IDs: {sorted(duplicates)}")

        # Validate that context references point to real step IDs
        for step in self.steps:
            for ref in step.context:
                if ref not in seen:
                    raise ValueError(
                        f"Step '{step.id}' references unknown step ID '{ref}' in context"
                    )

        return self

    @property
    def step_ids(self) -> list[str]:
        return [s.id for s in self.steps]

    def get_step(self, step_id: str) -> RunbookStep | None:
        for step in self.steps:
            if step.id == step_id:
                return step
        return None


# ---------------------------------------------------------------------------
# Template resolver
# ---------------------------------------------------------------------------

_TEMPLATE_RE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def _resolve_field_path(obj: Any, field_path: str) -> Any:
    """Traverse a dot-separated field path through objects and dicts.

    Examples::

        _resolve_field_path(incident, "id")            # → incident.id
        _resolve_field_path(incident, "metadata.host") # → incident.metadata["host"]
        _resolve_field_path({"a": {"b": 1}}, "a.b")   # → 1
    """
    current: Any = obj
    for part in field_path.split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
    return current


def resolve_template(
    value: str,
    incident: Incident,
    step_results: dict[str, Any] | None = None,
) -> str:
    """Replace ``{{ incident.field }}`` and ``{{ step_id.field }}`` placeholders.

    Supports nested field access:

    - ``{{ incident.id }}`` — direct attribute
    - ``{{ incident.metadata.host }}`` — nested dict access
    - ``{{ step_id.key }}`` — key in a step's result dict
    - ``{{ step_id.nested.key }}`` — nested key in a step's result dict

    Unresolvable references are left as-is so callers can detect them.
    """
    results = step_results or {}

    def _replace(match: re.Match[str]) -> str:
        expr = match.group(1)
        parts = expr.split(".", 1)
        if len(parts) != 2:
            return match.group(0)

        source, field = parts
        if source == "incident":
            val = _resolve_field_path(incident, field)
            if val is not None:
                return str(val)
            return match.group(0)

        # Step result reference
        step_result = results.get(source)
        if step_result is not None:
            val = _resolve_field_path(step_result, field)
            if val is not None:
                return str(val)

        return match.group(0)

    return _TEMPLATE_RE.sub(_replace, value)


def resolve_params(
    params: dict[str, Any],
    incident: Incident,
    step_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Recursively resolve all template placeholders inside a params dict."""
    results = step_results or {}
    resolved: dict[str, Any] = {}

    for key, val in params.items():
        if isinstance(val, str):
            resolved[key] = resolve_template(val, incident, results)
        elif isinstance(val, dict):
            resolved[key] = resolve_params(val, incident, results)
        elif isinstance(val, list):
            resolved[key] = [
                resolve_template(v, incident, results) if isinstance(v, str) else v
                for v in val
            ]
        else:
            resolved[key] = val

    return resolved


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class RunbookParser:
    """Loads and validates runbook definitions from YAML files."""

    @staticmethod
    def load_file(path: str | Path) -> Runbook:
        """Parse a single YAML file and return a validated Runbook.

        Raises:
            RunbookParseError: if the file cannot be read, is not valid YAML,
                or fails Pydantic validation.
        """
        path = Path(path)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RunbookParseError(str(path), f"Cannot read file: {exc}") from exc

        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise RunbookParseError(str(path), f"Invalid YAML: {exc}") from exc

        if not isinstance(data, dict):
            raise RunbookParseError(str(path), "Top-level value must be a YAML mapping")

        try:
            runbook = Runbook.model_validate(data)
        except Exception as exc:
            raise RunbookParseError(str(path), str(exc)) from exc

        runbook.source_path = str(path)
        return runbook

    @staticmethod
    def load_directory(directory: str | Path) -> list[Runbook]:
        """Load all ``*.yaml`` and ``*.yml`` files from a directory.

        Files that fail to parse are skipped with a logged warning; the caller
        receives only the successfully parsed runbooks.
        """
        directory = Path(directory)
        runbooks: list[Runbook] = []

        for yaml_path in sorted(directory.glob("*.yaml")) + sorted(
            directory.glob("*.yml")
        ):
            try:
                runbooks.append(RunbookParser.load_file(yaml_path))
            except RunbookParseError as exc:
                logger.warning("Skipping runbook '%s': %s", yaml_path.name, exc)

        return runbooks

    @staticmethod
    def list_runbooks(directory: str | Path) -> list[Path]:
        """Return paths for all YAML files in a directory without parsing them."""
        directory = Path(directory)
        return sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml"))


# ---------------------------------------------------------------------------
# Step executor — private helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _coerce_to_dict(value: Any) -> dict[str, Any]:
    """Normalise a provider method return value into a serialisable dict.

    - ``None``        → ``{}``
    - ``dict``        → as-is
    - ``BaseModel``   → ``.model_dump()``
    - ``list``        → ``{"items": [...], "count": N}``
    - anything else   → ``{"value": str(value)}``
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, list):
        items: list[Any] = []
        for item in value:
            if isinstance(item, BaseModel):
                items.append(item.model_dump())
            elif isinstance(item, dict):
                items.append(item)
            else:
                items.append({"value": str(item)})
        return {"items": items, "count": len(items)}
    return {"value": str(value)}


# ---------------------------------------------------------------------------
# Step execution models
# ---------------------------------------------------------------------------


class StepStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING_APPROVAL = "pending_approval"


class ExecutionStatus(str, Enum):
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class StepResult(BaseModel):
    """The outcome of executing a single runbook step."""

    step_id: str
    status: StepStatus = StepStatus.PENDING
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    executed_at: datetime | None = None
    skipped_reason: str | None = None


class RunbookExecution(BaseModel):
    """Tracks the complete state of a runbook execution run."""

    id: str
    runbook_name: str
    incident_id: str
    status: ExecutionStatus = ExecutionStatus.RUNNING
    # Per-step outcomes keyed by step ID
    step_results: dict[str, StepResult] = Field(default_factory=dict)
    # Raw result dicts accumulated for template resolution across steps
    results: dict[str, Any] = Field(default_factory=dict)
    # Step IDs currently blocked on operator approval
    pending_approval_steps: list[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime | None = None


# ---------------------------------------------------------------------------
# Step executor
# ---------------------------------------------------------------------------


class RunbookStepExecutor:
    """Executes individual runbook steps and full runbook workflows.

    Execution semantics
    -------------------
    - **gather** steps are non-fatal: a failed gather logs a warning and
      continues with an empty result dict for that step.
    - **execute** and **ml_decision** step failures are fatal and halt the
      workflow with ``ExecutionStatus.FAILED``.
    - Steps with ``requires_approval=True`` pause execution and return
      ``ExecutionStatus.AWAITING_APPROVAL``.  Call :meth:`resume_runbook`
      with the approved step IDs to continue.
    - A timeline entry is appended to ``incident.timeline`` for every step
      that is actually executed (success or failure).
    """

    def __init__(
        self,
        registry: Any,  # IntegrationRegistry — typed loosely to avoid heavy import
        ml_engine: Any,  # MLEngine
    ) -> None:
        self._registry = registry
        self._ml = ml_engine

    # ------------------------------------------------------------------
    # Public: single-step execution
    # ------------------------------------------------------------------

    async def execute_step(
        self,
        step: RunbookStep,
        incident: Incident,
        step_results: dict[str, Any],
    ) -> StepResult:
        """Execute one step and return its result.

        Does **not** check ``requires_approval`` — the approval gate is
        enforced by :meth:`execute_runbook` / :meth:`resume_runbook`.
        """
        if step.action == "ml_decision":
            return await self._run_ml_decision(step, incident, step_results)
        return await self._run_integration_step(step, incident, step_results)

    # ------------------------------------------------------------------
    # Public: full runbook execution
    # ------------------------------------------------------------------

    async def execute_runbook(
        self,
        runbook: Runbook,
        incident: Incident,
        pre_approved_steps: set[str] | None = None,
    ) -> RunbookExecution:
        """Execute all steps in *runbook* sequentially.

        Stops at the first step that requires approval and is not in
        ``pre_approved_steps``, returning the execution with
        ``status=AWAITING_APPROVAL`` and ``pending_approval_steps`` populated.
        """
        execution = RunbookExecution(
            id=f"exec-{_uid()}",
            runbook_name=runbook.name,
            incident_id=incident.id,
            status=ExecutionStatus.RUNNING,
            started_at=_now(),
        )
        return await self._run_steps(
            runbook,
            incident,
            execution,
            accumulated={},
            approved=pre_approved_steps or set(),
            start_index=0,
        )

    async def resume_runbook(
        self,
        runbook: Runbook,
        incident: Incident,
        execution: RunbookExecution,
        approved_step_ids: set[str],
    ) -> RunbookExecution:
        """Resume an ``AWAITING_APPROVAL`` execution after operator sign-off.

        *approved_step_ids* is the set of step IDs the operator approved in
        this call.  Execution continues until it completes or hits another
        unapproved gate.

        Returns *execution* unchanged if it is not in ``AWAITING_APPROVAL``
        state.
        """
        if execution.status != ExecutionStatus.AWAITING_APPROVAL:
            return execution

        execution.status = ExecutionStatus.RUNNING
        execution.pending_approval_steps = []

        # Find the first step not yet successfully completed.
        completed = {
            sid
            for sid, sr in execution.step_results.items()
            if sr.status == StepStatus.SUCCESS
        }
        start_index = len(runbook.steps)  # default: nothing left to do
        for i, step in enumerate(runbook.steps):
            if step.id not in completed:
                start_index = i
                break

        return await self._run_steps(
            runbook,
            incident,
            execution,
            accumulated=dict(execution.results),
            approved=approved_step_ids,
            start_index=start_index,
        )

    # ------------------------------------------------------------------
    # Internal: shared execution loop
    # ------------------------------------------------------------------

    async def _run_steps(
        self,
        runbook: Runbook,
        incident: Incident,
        execution: RunbookExecution,
        accumulated: dict[str, Any],
        approved: set[str],
        start_index: int,
    ) -> RunbookExecution:
        """Core step-execution loop shared by execute_runbook and resume_runbook."""
        for step in runbook.steps[start_index:]:

            # --- Approval gate -------------------------------------------
            if step.requires_approval and step.id not in approved:
                execution.step_results[step.id] = StepResult(
                    step_id=step.id,
                    status=StepStatus.PENDING_APPROVAL,
                    skipped_reason="Awaiting operator approval",
                )
                execution.pending_approval_steps.append(step.id)

                # Mark subsequent steps as pending so the caller sees the full picture
                gate_index = runbook.steps.index(step)
                for subsequent in runbook.steps[gate_index + 1 :]:
                    if subsequent.id not in execution.step_results:
                        execution.step_results[subsequent.id] = StepResult(
                            step_id=subsequent.id,
                            status=StepStatus.PENDING,
                            skipped_reason="Blocked by unapproved step",
                        )
                    if subsequent.requires_approval:
                        execution.pending_approval_steps.append(subsequent.id)

                execution.status = ExecutionStatus.AWAITING_APPROVAL
                execution.results = accumulated
                return execution

            # --- Execute step --------------------------------------------
            step_result = await self.execute_step(step, incident, accumulated)
            execution.step_results[step.id] = step_result
            self._append_timeline(incident, step, step_result)

            if step_result.status == StepStatus.SUCCESS:
                accumulated[step.id] = step_result.result

            elif step_result.status == StepStatus.FAILED:
                if step.action == "gather":
                    # Non-fatal: log and continue with an empty result dict
                    logger.warning(
                        "Runbook '%s': gather step '%s' failed (%s) — continuing",
                        runbook.name,
                        step.id,
                        step_result.error,
                    )
                    accumulated[step.id] = {}
                else:
                    # Fatal: execute / ml_decision failures stop the workflow
                    execution.status = ExecutionStatus.FAILED
                    execution.completed_at = _now()
                    execution.results = accumulated
                    return execution

        # All steps processed without an early return → complete
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = _now()
        execution.results = accumulated
        return execution

    # ------------------------------------------------------------------
    # Internal: step-type handlers
    # ------------------------------------------------------------------

    async def _run_integration_step(
        self,
        step: RunbookStep,
        incident: Incident,
        step_results: dict[str, Any],
    ) -> StepResult:
        """Call an integration provider method and coerce the result to a dict."""
        resolved_params = resolve_params(step.params, incident, step_results)

        try:
            provider = self._registry.get_provider(step.integration)
        except Exception as exc:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=f"Provider not found for '{step.integration}': {exc}",
                executed_at=_now(),
            )

        method_fn = getattr(provider, step.method, None)
        if method_fn is None:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=f"Method '{step.method}' not found on {step.integration} provider",
                executed_at=_now(),
            )

        try:
            raw = await method_fn(**resolved_params)
        except Exception as exc:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=str(exc),
                executed_at=_now(),
            )

        return StepResult(
            step_id=step.id,
            status=StepStatus.SUCCESS,
            result=_coerce_to_dict(raw),
            executed_at=_now(),
        )

    async def _run_ml_decision(
        self,
        step: RunbookStep,
        incident: Incident,
        step_results: dict[str, Any],
    ) -> StepResult:
        """Invoke the ML engine using referenced step results as synthetic findings."""
        findings: list[Finding] = []
        for ref in step.context:
            ref_data = step_results.get(ref)
            if ref_data:
                findings.append(
                    Finding(
                        id=f"rb-{ref}",
                        finding_type=FindingType.CORRELATION,
                        source=f"runbook_step:{ref}",
                        summary=f"Data gathered by runbook step '{ref}'",
                        details=ref_data if isinstance(ref_data, dict) else {"value": str(ref_data)},
                        confidence=0.8,
                        timestamp=_now(),
                    )
                )

        try:
            diagnosis = await self._ml.diagnose(incident.description, findings)
        except Exception as exc:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=str(exc),
                executed_at=_now(),
            )

        return StepResult(
            step_id=step.id,
            status=StepStatus.SUCCESS,
            result=diagnosis.model_dump(),
            executed_at=_now(),
        )

    # ------------------------------------------------------------------
    # Internal: timeline
    # ------------------------------------------------------------------

    @staticmethod
    def _append_timeline(
        incident: Incident,
        step: RunbookStep,
        result: StepResult,
    ) -> None:
        """Append a timeline entry to the incident for an executed step."""
        ok = result.status == StepStatus.SUCCESS
        incident.timeline.append(
            TimelineEntry(
                timestamp=result.executed_at or _now(),
                event_type=f"runbook_step_{'success' if ok else 'failed'}",
                summary=f"{'✓' if ok else '✗'} [{step.action}] {step.description}",
                source="runbook_engine",
                details={
                    "step_id": step.id,
                    "integration": step.integration,
                    "method": step.method,
                    **({"error": result.error} if result.error else {}),
                },
            )
        )
