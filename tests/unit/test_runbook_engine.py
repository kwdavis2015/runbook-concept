"""Tests for core/runbook_engine.py — parser, models, and template resolver."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.exceptions import RunbookParseError
from core.models import (
    DiagnosticResult,
    HostInfo,
    Incident,
    IncidentStatus,
    ProblemCategory,
    RiskLevel,
    Severity,
)
from core.runbook_engine import (
    VALID_INTEGRATIONS,
    VALID_METHODS,
    ExecutionStatus,
    Runbook,
    RunbookExecution,
    RunbookParser,
    RunbookStep,
    RunbookStepExecutor,
    StepResult,
    StepStatus,
    _coerce_to_dict,
    _resolve_field_path,
    resolve_params,
    resolve_template,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_incident(**kwargs) -> Incident:
    defaults = dict(
        id="INC-test",
        title="Test incident",
        status=IncidentStatus.DIAGNOSING,
        severity=Severity.HIGH,
        category=ProblemCategory.COMPUTE,
        metadata={"host": "prod-web-03", "service": "java"},
    )
    defaults.update(kwargs)
    return Incident(**defaults)


def _gather_step(**kwargs) -> dict:
    base = dict(
        id="s1",
        action="gather",
        description="Get alerts",
        integration="monitoring",
        method="get_current_alerts",
        params={},
    )
    base.update(kwargs)
    return base


def _write_yaml(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content))
    return p


# ---------------------------------------------------------------------------
# RunbookStep — action validation
# ---------------------------------------------------------------------------


class TestRunbookStepActionValidation:
    def test_valid_gather_step(self):
        step = RunbookStep(**_gather_step())
        assert step.action == "gather"
        assert step.integration == "monitoring"

    def test_valid_execute_step(self):
        step = RunbookStep(
            id="s1",
            action="execute",
            description="Restart service",
            integration="compute",
            method="restart_service",
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
        )
        assert step.action == "execute"
        assert step.requires_approval is True

    def test_valid_ml_decision_step(self):
        step = RunbookStep(
            id="decide",
            action="ml_decision",
            description="Decide",
            context=["s1", "s2"],
        )
        assert step.action == "ml_decision"
        assert step.context == ["s1", "s2"]

    def test_invalid_action_raises(self):
        with pytest.raises(Exception, match="invalid action 'invent'"):
            RunbookStep(**_gather_step(action="invent"))

    def test_gather_missing_integration_raises(self):
        with pytest.raises(Exception, match="requires 'integration'"):
            RunbookStep(id="s1", action="gather", description="x")

    def test_gather_missing_method_raises(self):
        with pytest.raises(Exception, match="requires 'method'"):
            RunbookStep(id="s1", action="gather", description="x", integration="monitoring")

    def test_unknown_integration_raises(self):
        with pytest.raises(Exception, match="unknown integration 'datadog'"):
            RunbookStep(**_gather_step(integration="datadog"))

    def test_unknown_method_raises(self):
        with pytest.raises(Exception, match="unknown method 'get_zombies'"):
            RunbookStep(**_gather_step(method="get_zombies"))

    def test_ml_decision_needs_no_integration(self):
        # ml_decision steps must NOT require integration/method
        step = RunbookStep(id="d", action="ml_decision", description="decide", context=[])
        assert step.integration is None
        assert step.method is None

    def test_default_risk_level_is_low(self):
        step = RunbookStep(**_gather_step())
        assert step.risk_level == RiskLevel.LOW

    def test_params_default_empty(self):
        step = RunbookStep(**_gather_step())
        assert step.params == {}

    def test_context_default_empty(self):
        step = RunbookStep(**_gather_step())
        assert step.context == []


# ---------------------------------------------------------------------------
# RunbookStep — per-integration method coverage
# ---------------------------------------------------------------------------


class TestRunbookStepMethodCoverage:
    @pytest.mark.parametrize("method", sorted(VALID_METHODS["monitoring"]))
    def test_all_monitoring_methods(self, method):
        RunbookStep(
            id="s", action="gather", description="x",
            integration="monitoring", method=method,
        )

    @pytest.mark.parametrize("method", sorted(VALID_METHODS["ticketing"]))
    def test_all_ticketing_methods(self, method):
        RunbookStep(
            id="s", action="gather", description="x",
            integration="ticketing", method=method,
        )

    @pytest.mark.parametrize("method", sorted(VALID_METHODS["alerting"]))
    def test_all_alerting_methods(self, method):
        RunbookStep(
            id="s", action="gather", description="x",
            integration="alerting", method=method,
        )

    @pytest.mark.parametrize("method", sorted(VALID_METHODS["compute"]))
    def test_all_compute_methods(self, method):
        RunbookStep(
            id="s", action="gather", description="x",
            integration="compute", method=method,
        )

    @pytest.mark.parametrize("method", sorted(VALID_METHODS["communication"]))
    def test_all_communication_methods(self, method):
        RunbookStep(
            id="s", action="execute", description="x",
            integration="communication", method=method,
        )


# ---------------------------------------------------------------------------
# Runbook — structural validation
# ---------------------------------------------------------------------------


class TestRunbookValidation:
    def _minimal_runbook(self, steps=None) -> dict:
        return {
            "name": "Test Runbook",
            "steps": steps or [_gather_step()],
        }

    def test_valid_minimal_runbook(self):
        rb = Runbook.model_validate(self._minimal_runbook())
        assert rb.name == "Test Runbook"
        assert len(rb.steps) == 1

    def test_optional_fields_default(self):
        rb = Runbook.model_validate(self._minimal_runbook())
        assert rb.description == ""
        assert rb.trigger is None
        assert rb.severity is None
        assert rb.category is None
        assert rb.tags == []
        assert rb.source_path is None

    def test_full_metadata(self):
        data = self._minimal_runbook()
        data.update(
            description="A runbook",
            trigger="cpu > 90%",
            severity="high",
            category="compute",
            tags=["cpu", "prod"],
        )
        rb = Runbook.model_validate(data)
        assert rb.severity == Severity.HIGH
        assert rb.category == ProblemCategory.COMPUTE
        assert rb.tags == ["cpu", "prod"]

    def test_duplicate_step_ids_raise(self):
        steps = [_gather_step(id="s1"), _gather_step(id="s1", method="get_logs")]
        with pytest.raises(Exception, match="Duplicate step IDs"):
            Runbook.model_validate(self._minimal_runbook(steps=steps))

    def test_invalid_context_reference_raises(self):
        steps = [
            _gather_step(id="s1"),
            {
                "id": "decide",
                "action": "ml_decision",
                "description": "decide",
                "context": ["s1", "ghost_step"],
            },
        ]
        with pytest.raises(Exception, match="unknown step ID 'ghost_step'"):
            Runbook.model_validate(self._minimal_runbook(steps=steps))

    def test_valid_context_reference(self):
        steps = [
            _gather_step(id="gather_logs"),
            {
                "id": "decide",
                "action": "ml_decision",
                "description": "decide",
                "context": ["gather_logs"],
            },
        ]
        rb = Runbook.model_validate(self._minimal_runbook(steps=steps))
        assert rb.steps[1].context == ["gather_logs"]

    def test_step_ids_property(self):
        steps = [_gather_step(id="a"), _gather_step(id="b", method="get_logs")]
        rb = Runbook.model_validate(self._minimal_runbook(steps=steps))
        assert rb.step_ids == ["a", "b"]

    def test_get_step_found(self):
        rb = Runbook.model_validate(self._minimal_runbook())
        assert rb.get_step("s1") is not None
        assert rb.get_step("s1").id == "s1"

    def test_get_step_not_found(self):
        rb = Runbook.model_validate(self._minimal_runbook())
        assert rb.get_step("nonexistent") is None


# ---------------------------------------------------------------------------
# Template resolver
# ---------------------------------------------------------------------------


class TestResolveTemplate:
    def setup_method(self):
        self.incident = _make_incident()

    def test_incident_field(self):
        result = resolve_template("{{ incident.id }}", self.incident)
        assert result == "INC-test"

    def test_incident_title(self):
        result = resolve_template("Host: {{ incident.title }}", self.incident)
        assert result == "Host: Test incident"

    def test_step_result_reference(self):
        step_results = {"diagnose": {"target_service": "java"}}
        result = resolve_template("{{ diagnose.target_service }}", self.incident, step_results)
        assert result == "java"

    def test_unknown_incident_field_preserved(self):
        result = resolve_template("{{ incident.nonexistent }}", self.incident)
        assert result == "{{ incident.nonexistent }}"

    def test_unknown_step_preserved(self):
        result = resolve_template("{{ ghost_step.field }}", self.incident)
        assert result == "{{ ghost_step.field }}"

    def test_missing_step_result_field_preserved(self):
        step_results = {"diagnose": {"other_key": "x"}}
        result = resolve_template("{{ diagnose.missing }}", self.incident, step_results)
        assert result == "{{ diagnose.missing }}"

    def test_no_template_passthrough(self):
        result = resolve_template("plain string", self.incident)
        assert result == "plain string"

    def test_whitespace_in_template(self):
        result = resolve_template("{{  incident.id  }}", self.incident)
        assert result == "INC-test"

    def test_multiple_placeholders(self):
        step_results = {"s": {"svc": "redis"}}
        result = resolve_template(
            "{{ incident.id }} on {{ s.svc }}", self.incident, step_results
        )
        assert result == "INC-test on redis"

    def test_no_step_results_defaults_to_empty(self):
        result = resolve_template("{{ incident.id }}", self.incident, None)
        assert result == "INC-test"


class TestResolveParams:
    def setup_method(self):
        self.incident = _make_incident()

    def test_simple_string_param(self):
        params = {"host": "{{ incident.id }}"}
        resolved = resolve_params(params, self.incident)
        assert resolved["host"] == "INC-test"

    def test_non_string_param_unchanged(self):
        params = {"limit": 10, "enabled": True, "ratio": 0.5}
        resolved = resolve_params(params, self.incident)
        assert resolved == {"limit": 10, "enabled": True, "ratio": 0.5}

    def test_nested_dict(self):
        params = {"outer": {"inner": "{{ incident.id }}"}}
        resolved = resolve_params(params, self.incident)
        assert resolved["outer"]["inner"] == "INC-test"

    def test_list_of_strings(self):
        params = {"hosts": ["{{ incident.id }}", "static"]}
        resolved = resolve_params(params, self.incident)
        assert resolved["hosts"] == ["INC-test", "static"]

    def test_list_non_strings_unchanged(self):
        params = {"counts": [1, 2, 3]}
        resolved = resolve_params(params, self.incident)
        assert resolved["counts"] == [1, 2, 3]

    def test_step_result_in_params(self):
        step_results = {"diagnose": {"target_service": "tomcat"}}
        params = {"service": "{{ diagnose.target_service }}"}
        resolved = resolve_params(params, self.incident, step_results)
        assert resolved["service"] == "tomcat"

    def test_empty_params(self):
        assert resolve_params({}, self.incident) == {}


# ---------------------------------------------------------------------------
# RunbookParser — file loading
# ---------------------------------------------------------------------------


class TestRunbookParserLoadFile:
    _VALID_YAML = """\
        name: My Runbook
        description: A test runbook
        trigger: "cpu > 90%"
        severity: high
        steps:
          - id: gather_alerts
            action: gather
            description: Get alerts
            integration: monitoring
            method: get_current_alerts
            params: {}
          - id: decide
            action: ml_decision
            description: Decide
            context:
              - gather_alerts
    """

    def test_load_valid_file(self, tmp_path):
        p = _write_yaml(tmp_path, "test.yaml", self._VALID_YAML)
        rb = RunbookParser.load_file(p)
        assert rb.name == "My Runbook"
        assert len(rb.steps) == 2
        assert rb.source_path == str(p)
        assert rb.severity == Severity.HIGH

    def test_source_path_is_set(self, tmp_path):
        p = _write_yaml(tmp_path, "test.yaml", self._VALID_YAML)
        rb = RunbookParser.load_file(p)
        assert rb.source_path == str(p)

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(RunbookParseError, match="Cannot read file"):
            RunbookParser.load_file(tmp_path / "ghost.yaml")

    def test_invalid_yaml_raises(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("name: [unclosed bracket")
        with pytest.raises(RunbookParseError, match="Invalid YAML"):
            RunbookParser.load_file(p)

    def test_non_mapping_yaml_raises(self, tmp_path):
        p = tmp_path / "list.yaml"
        p.write_text("- item1\n- item2\n")
        with pytest.raises(RunbookParseError, match="must be a YAML mapping"):
            RunbookParser.load_file(p)

    def test_validation_error_raises_parse_error(self, tmp_path):
        p = _write_yaml(
            tmp_path,
            "bad_step.yaml",
            """\
            name: Bad
            steps:
              - id: s1
                action: invalid_action
                description: oops
            """,
        )
        with pytest.raises(RunbookParseError):
            RunbookParser.load_file(p)

    def test_accepts_path_string(self, tmp_path):
        p = _write_yaml(tmp_path, "test.yaml", self._VALID_YAML)
        rb = RunbookParser.load_file(str(p))  # string path
        assert rb.name == "My Runbook"


# ---------------------------------------------------------------------------
# RunbookParser — directory loading
# ---------------------------------------------------------------------------


class TestRunbookParserLoadDirectory:
    _GOOD = """\
        name: Good Runbook
        steps:
          - id: s1
            action: gather
            description: Get alerts
            integration: monitoring
            method: get_current_alerts
    """
    _BAD = "name: [invalid yaml"

    def test_loads_all_valid_files(self, tmp_path):
        _write_yaml(tmp_path, "a.yaml", self._GOOD)
        _write_yaml(tmp_path, "b.yaml", self._GOOD)
        runbooks = RunbookParser.load_directory(tmp_path)
        assert len(runbooks) == 2

    def test_skips_invalid_files(self, tmp_path):
        _write_yaml(tmp_path, "good.yaml", self._GOOD)
        bad = tmp_path / "bad.yaml"
        bad.write_text(self._BAD)
        runbooks = RunbookParser.load_directory(tmp_path)
        assert len(runbooks) == 1
        assert runbooks[0].name == "Good Runbook"

    def test_empty_directory(self, tmp_path):
        assert RunbookParser.load_directory(tmp_path) == []

    def test_ignores_non_yaml_files(self, tmp_path):
        _write_yaml(tmp_path, "runbook.yaml", self._GOOD)
        (tmp_path / "notes.txt").write_text("not a runbook")
        (tmp_path / "data.json").write_text("{}")
        runbooks = RunbookParser.load_directory(tmp_path)
        assert len(runbooks) == 1

    def test_accepts_yml_extension(self, tmp_path):
        p = tmp_path / "rb.yml"
        p.write_text(textwrap.dedent(self._GOOD))
        runbooks = RunbookParser.load_directory(tmp_path)
        assert len(runbooks) == 1

    def test_results_are_sorted(self, tmp_path):
        _write_yaml(tmp_path, "zebra.yaml", self._GOOD)
        _write_yaml(tmp_path, "alpha.yaml", self._GOOD)
        runbooks = RunbookParser.load_directory(tmp_path)
        paths = [rb.source_path for rb in runbooks]
        assert paths == sorted(paths)


# ---------------------------------------------------------------------------
# RunbookParser.list_runbooks
# ---------------------------------------------------------------------------


class TestRunbookParserListRunbooks:
    def test_lists_yaml_files(self, tmp_path):
        (tmp_path / "a.yaml").write_text("name: A")
        (tmp_path / "b.yml").write_text("name: B")
        (tmp_path / "c.txt").write_text("name: C")
        paths = RunbookParser.list_runbooks(tmp_path)
        names = {p.name for p in paths}
        assert "a.yaml" in names
        assert "b.yml" in names
        assert "c.txt" not in names

    def test_empty_directory(self, tmp_path):
        assert RunbookParser.list_runbooks(tmp_path) == []


# ---------------------------------------------------------------------------
# Integration: load the real runbooks/ directory
# ---------------------------------------------------------------------------


class TestRealRunbookFiles:
    """Smoke-test all YAML files that ship with the project."""

    def test_runbooks_directory_parses_cleanly(self):
        runbooks_dir = Path(__file__).parents[2] / "runbooks"
        if not runbooks_dir.exists():
            pytest.skip("runbooks/ directory not found")

        runbooks = RunbookParser.load_directory(runbooks_dir)
        assert len(runbooks) > 0, "Expected at least one runbook to load"

        for rb in runbooks:
            assert rb.name, f"Runbook from {rb.source_path} has no name"
            assert rb.steps, f"Runbook '{rb.name}' has no steps"

    def test_high_cpu_runbook(self):
        path = Path(__file__).parents[2] / "runbooks" / "high_cpu_troubleshooting.yaml"
        if not path.exists():
            pytest.skip("high_cpu_troubleshooting.yaml not found")

        rb = RunbookParser.load_file(path)
        assert rb.name == "High CPU Troubleshooting"
        assert rb.severity == Severity.HIGH
        assert rb.category == ProblemCategory.COMPUTE
        assert any(s.action == "ml_decision" for s in rb.steps)
        assert any(s.requires_approval for s in rb.steps)

    def test_network_runbook_has_valid_context_refs(self):
        path = Path(__file__).parents[2] / "runbooks" / "network_troubleshooting.yaml"
        if not path.exists():
            pytest.skip("network_troubleshooting.yaml not found")

        rb = RunbookParser.load_file(path)
        step_ids = set(rb.step_ids)
        for step in rb.steps:
            for ref in step.context:
                assert ref in step_ids, f"Broken context ref '{ref}' in step '{step.id}'"


# ---------------------------------------------------------------------------
# _resolve_field_path
# ---------------------------------------------------------------------------


class TestResolveFieldPath:
    def test_direct_attribute(self):
        inc = _make_incident()
        assert _resolve_field_path(inc, "id") == "INC-test"

    def test_nested_dict_attribute(self):
        inc = _make_incident()
        assert _resolve_field_path(inc, "metadata.host") == "prod-web-03"

    def test_dict_key(self):
        d = {"a": {"b": 42}}
        assert _resolve_field_path(d, "a.b") == 42

    def test_missing_key_returns_none(self):
        assert _resolve_field_path({"x": 1}, "missing") is None

    def test_none_object_returns_none(self):
        assert _resolve_field_path(None, "anything") is None

    def test_intermediate_none_returns_none(self):
        d = {"a": None}
        assert _resolve_field_path(d, "a.b") is None

    def test_single_segment(self):
        assert _resolve_field_path({"key": "val"}, "key") == "val"


# ---------------------------------------------------------------------------
# Nested template resolution (new in executor phase)
# ---------------------------------------------------------------------------


class TestResolveTemplateNested:
    def setup_method(self):
        self.incident = _make_incident()

    def test_nested_incident_field(self):
        result = resolve_template("{{ incident.metadata.host }}", self.incident)
        assert result == "prod-web-03"

    def test_nested_incident_service(self):
        result = resolve_template("{{ incident.metadata.service }}", self.incident)
        assert result == "java"

    def test_nested_step_result(self):
        step_results = {"diagnose": {"nested": {"key": "value"}}}
        result = resolve_template("{{ diagnose.nested.key }}", self.incident, step_results)
        assert result == "value"

    def test_missing_nested_key_preserved(self):
        result = resolve_template("{{ incident.metadata.nonexistent }}", self.incident)
        assert result == "{{ incident.metadata.nonexistent }}"


# ---------------------------------------------------------------------------
# _coerce_to_dict
# ---------------------------------------------------------------------------


class TestCoerceToDict:
    def test_none_returns_empty(self):
        assert _coerce_to_dict(None) == {}

    def test_dict_passthrough(self):
        d = {"a": 1}
        assert _coerce_to_dict(d) is d

    def test_pydantic_model(self):
        host = HostInfo(hostname="web-01")
        result = _coerce_to_dict(host)
        assert result["hostname"] == "web-01"
        assert isinstance(result, dict)

    def test_list_of_pydantic_models(self):
        hosts = [HostInfo(hostname="web-01"), HostInfo(hostname="web-02")]
        result = _coerce_to_dict(hosts)
        assert result["count"] == 2
        assert result["items"][0]["hostname"] == "web-01"

    def test_empty_list(self):
        assert _coerce_to_dict([]) == {"items": [], "count": 0}

    def test_list_of_dicts(self):
        result = _coerce_to_dict([{"id": "a"}, {"id": "b"}])
        assert result["count"] == 2
        assert result["items"][0]["id"] == "a"

    def test_scalar_wrapped(self):
        result = _coerce_to_dict("hello")
        assert result == {"value": "hello"}

    def test_int_wrapped(self):
        result = _coerce_to_dict(42)
        assert result == {"value": "42"}

    def test_list_of_mixed_types(self):
        result = _coerce_to_dict([HostInfo(hostname="h1"), {"raw": True}, "string"])
        assert result["count"] == 3
        assert result["items"][0]["hostname"] == "h1"
        assert result["items"][1] == {"raw": True}
        assert result["items"][2] == {"value": "string"}


# ---------------------------------------------------------------------------
# StepResult and RunbookExecution models
# ---------------------------------------------------------------------------


class TestStepResult:
    def test_defaults(self):
        sr = StepResult(step_id="s1")
        assert sr.status == StepStatus.PENDING
        assert sr.result == {}
        assert sr.error is None
        assert sr.executed_at is None
        assert sr.skipped_reason is None

    def test_success(self):
        sr = StepResult(step_id="s1", status=StepStatus.SUCCESS, result={"k": "v"})
        assert sr.status == StepStatus.SUCCESS
        assert sr.result["k"] == "v"

    def test_failed(self):
        sr = StepResult(step_id="s1", status=StepStatus.FAILED, error="boom")
        assert sr.status == StepStatus.FAILED
        assert sr.error == "boom"


class TestRunbookExecution:
    def test_defaults(self):
        from datetime import datetime, timezone

        ex = RunbookExecution(
            id="exec-1",
            runbook_name="Test",
            incident_id="INC-1",
            started_at=datetime.now(timezone.utc),
        )
        assert ex.status == ExecutionStatus.RUNNING
        assert ex.step_results == {}
        assert ex.results == {}
        assert ex.pending_approval_steps == []
        assert ex.completed_at is None


# ---------------------------------------------------------------------------
# RunbookStepExecutor fixtures
# ---------------------------------------------------------------------------


def _mock_registry(return_value=None) -> MagicMock:
    """Return a MagicMock registry whose provider returns a stub with common methods."""
    registry = MagicMock()
    provider = MagicMock()
    provider.get_current_alerts = AsyncMock(return_value=return_value or [])
    provider.get_host_info = AsyncMock(return_value=HostInfo(hostname="web-01"))
    provider.get_logs = AsyncMock(return_value=[])
    provider.restart_service = AsyncMock(return_value={"status": "success"})
    provider.send_message = AsyncMock(return_value=None)
    registry.get_provider.return_value = provider
    return registry


def _mock_ml(diagnosis: DiagnosticResult | None = None) -> MagicMock:
    ml = MagicMock()
    ml.diagnose = AsyncMock(
        return_value=diagnosis
        or DiagnosticResult(
            root_cause="Memory leak",
            evidence_summary="Evidence",
            confidence=0.9,
        )
    )
    return ml


def _make_gather_runbook(step_id: str = "gather") -> Runbook:
    return Runbook(
        name="Test",
        steps=[
            RunbookStep(
                id=step_id,
                action="gather",
                description="Get alerts",
                integration="monitoring",
                method="get_current_alerts",
            )
        ],
    )


def _make_execute_runbook(requires_approval: bool = False) -> Runbook:
    return Runbook(
        name="Test",
        steps=[
            RunbookStep(
                id="do_it",
                action="execute",
                description="Restart service",
                integration="compute",
                method="restart_service",
                requires_approval=requires_approval,
                risk_level=RiskLevel.MEDIUM,
                params={"hostname": "web-01", "service": "java"},
            )
        ],
    )


# ---------------------------------------------------------------------------
# RunbookStepExecutor.execute_step
# ---------------------------------------------------------------------------


class TestExecuteStep:
    @pytest.mark.asyncio
    async def test_gather_success_returns_coerced_dict(self):
        registry = _mock_registry(return_value=[])
        executor = RunbookStepExecutor(registry=registry, ml_engine=_mock_ml())
        step = RunbookStep(
            id="s",
            action="gather",
            description="x",
            integration="monitoring",
            method="get_current_alerts",
        )
        result = await executor.execute_step(step, _make_incident(), {})
        assert result.status == StepStatus.SUCCESS
        assert result.step_id == "s"
        assert result.executed_at is not None

    @pytest.mark.asyncio
    async def test_gather_list_result_coerced(self):
        registry = _mock_registry(return_value=[HostInfo(hostname="h1")])
        executor = RunbookStepExecutor(registry=registry, ml_engine=_mock_ml())
        step = RunbookStep(
            id="s",
            action="gather",
            description="x",
            integration="monitoring",
            method="get_current_alerts",
        )
        result = await executor.execute_step(step, _make_incident(), {})
        assert result.status == StepStatus.SUCCESS
        assert result.result["count"] == 1

    @pytest.mark.asyncio
    async def test_gather_provider_not_found_returns_failed(self):
        registry = MagicMock()
        registry.get_provider.side_effect = Exception("no such provider")
        executor = RunbookStepExecutor(registry=registry, ml_engine=_mock_ml())
        step = RunbookStep(
            id="s",
            action="gather",
            description="x",
            integration="monitoring",
            method="get_current_alerts",
        )
        result = await executor.execute_step(step, _make_incident(), {})
        assert result.status == StepStatus.FAILED
        assert "Provider not found" in result.error

    @pytest.mark.asyncio
    async def test_gather_missing_method_returns_failed(self):
        registry = _mock_registry()
        del registry.get_provider.return_value.get_current_alerts  # remove the attr
        registry.get_provider.return_value.get_current_alerts = None  # set to None explicitly
        executor = RunbookStepExecutor(registry=registry, ml_engine=_mock_ml())
        step = RunbookStep(
            id="s",
            action="gather",
            description="x",
            integration="monitoring",
            method="get_current_alerts",
        )
        result = await executor.execute_step(step, _make_incident(), {})
        assert result.status == StepStatus.FAILED
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_gather_method_raises_returns_failed(self):
        registry = _mock_registry()
        registry.get_provider.return_value.get_current_alerts = AsyncMock(
            side_effect=RuntimeError("API down")
        )
        executor = RunbookStepExecutor(registry=registry, ml_engine=_mock_ml())
        step = RunbookStep(
            id="s",
            action="gather",
            description="x",
            integration="monitoring",
            method="get_current_alerts",
        )
        result = await executor.execute_step(step, _make_incident(), {})
        assert result.status == StepStatus.FAILED
        assert "API down" in result.error

    @pytest.mark.asyncio
    async def test_execute_step_success(self):
        registry = _mock_registry()
        executor = RunbookStepExecutor(registry=registry, ml_engine=_mock_ml())
        step = RunbookStep(
            id="s",
            action="execute",
            description="Restart",
            integration="compute",
            method="restart_service",
            params={"hostname": "web-01", "service": "java"},
        )
        result = await executor.execute_step(step, _make_incident(), {})
        assert result.status == StepStatus.SUCCESS
        assert result.result["status"] == "success"

    @pytest.mark.asyncio
    async def test_params_are_template_resolved(self):
        registry = _mock_registry()
        executor = RunbookStepExecutor(registry=registry, ml_engine=_mock_ml())
        step = RunbookStep(
            id="s",
            action="gather",
            description="Get host",
            integration="compute",
            method="get_host_info",
            params={"hostname": "{{ incident.metadata.host }}"},
        )
        incident = _make_incident()
        await executor.execute_step(step, incident, {})
        registry.get_provider.return_value.get_host_info.assert_called_once_with(
            hostname="prod-web-03"
        )

    @pytest.mark.asyncio
    async def test_ml_decision_calls_diagnose(self):
        ml = _mock_ml()
        executor = RunbookStepExecutor(registry=_mock_registry(), ml_engine=ml)
        step = RunbookStep(
            id="decide",
            action="ml_decision",
            description="Decide",
            context=["gather"],
        )
        step_results = {"gather": {"items": [{"name": "CPU alert"}], "count": 1}}
        result = await executor.execute_step(step, _make_incident(), step_results)
        assert result.status == StepStatus.SUCCESS
        ml.diagnose.assert_called_once()
        # The finding built from the gather result should be in the call
        _, findings = ml.diagnose.call_args.args
        assert len(findings) == 1
        assert findings[0].source == "runbook_step:gather"

    @pytest.mark.asyncio
    async def test_ml_decision_empty_context_calls_diagnose_with_no_findings(self):
        ml = _mock_ml()
        executor = RunbookStepExecutor(registry=_mock_registry(), ml_engine=ml)
        step = RunbookStep(id="d", action="ml_decision", description="x", context=[])
        result = await executor.execute_step(step, _make_incident(), {})
        assert result.status == StepStatus.SUCCESS
        _, findings = ml.diagnose.call_args.args
        assert findings == []

    @pytest.mark.asyncio
    async def test_ml_decision_engine_failure_returns_failed(self):
        ml = MagicMock()
        ml.diagnose = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        executor = RunbookStepExecutor(registry=_mock_registry(), ml_engine=ml)
        step = RunbookStep(id="d", action="ml_decision", description="x")
        result = await executor.execute_step(step, _make_incident(), {})
        assert result.status == StepStatus.FAILED
        assert "LLM unavailable" in result.error

    @pytest.mark.asyncio
    async def test_ml_decision_result_is_serialisable_dict(self):
        executor = RunbookStepExecutor(registry=_mock_registry(), ml_engine=_mock_ml())
        step = RunbookStep(id="d", action="ml_decision", description="x")
        result = await executor.execute_step(step, _make_incident(), {})
        assert "root_cause" in result.result
        assert result.result["root_cause"] == "Memory leak"


# ---------------------------------------------------------------------------
# RunbookStepExecutor.execute_runbook — full workflow
# ---------------------------------------------------------------------------


class TestExecuteRunbook:
    @pytest.mark.asyncio
    async def test_all_steps_succeed_status_completed(self):
        executor = RunbookStepExecutor(registry=_mock_registry(), ml_engine=_mock_ml())
        rb = _make_gather_runbook()
        incident = _make_incident()
        ex = await executor.execute_runbook(rb, incident)
        assert ex.status == ExecutionStatus.COMPLETED
        assert ex.completed_at is not None
        assert ex.step_results["gather"].status == StepStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_accumulated_results_stored_in_execution(self):
        executor = RunbookStepExecutor(registry=_mock_registry(), ml_engine=_mock_ml())
        rb = _make_gather_runbook()
        ex = await executor.execute_runbook(rb, _make_incident())
        assert "gather" in ex.results

    @pytest.mark.asyncio
    async def test_approval_gate_pauses_execution(self):
        executor = RunbookStepExecutor(registry=_mock_registry(), ml_engine=_mock_ml())
        rb = _make_execute_runbook(requires_approval=True)
        ex = await executor.execute_runbook(rb, _make_incident())
        assert ex.status == ExecutionStatus.AWAITING_APPROVAL
        assert "do_it" in ex.pending_approval_steps
        assert ex.step_results["do_it"].status == StepStatus.PENDING_APPROVAL
        assert ex.completed_at is None

    @pytest.mark.asyncio
    async def test_pre_approved_steps_bypass_gate(self):
        executor = RunbookStepExecutor(registry=_mock_registry(), ml_engine=_mock_ml())
        rb = _make_execute_runbook(requires_approval=True)
        ex = await executor.execute_runbook(
            rb, _make_incident(), pre_approved_steps={"do_it"}
        )
        assert ex.status == ExecutionStatus.COMPLETED
        assert ex.step_results["do_it"].status == StepStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_subsequent_steps_marked_pending_at_gate(self):
        """Steps after an unapproved gate should be marked PENDING."""
        rb = Runbook(
            name="Multi",
            steps=[
                RunbookStep(
                    id="gather",
                    action="gather",
                    description="gather",
                    integration="monitoring",
                    method="get_current_alerts",
                ),
                RunbookStep(
                    id="execute",
                    action="execute",
                    description="exec",
                    integration="compute",
                    method="restart_service",
                    requires_approval=True,
                    params={"hostname": "h", "service": "s"},
                ),
                RunbookStep(
                    id="notify",
                    action="execute",
                    description="notify",
                    integration="communication",
                    method="send_message",
                    params={"channel": "c", "message": "m"},
                ),
            ],
        )
        executor = RunbookStepExecutor(registry=_mock_registry(), ml_engine=_mock_ml())
        ex = await executor.execute_runbook(rb, _make_incident())
        assert ex.status == ExecutionStatus.AWAITING_APPROVAL
        assert ex.step_results["gather"].status == StepStatus.SUCCESS
        assert ex.step_results["execute"].status == StepStatus.PENDING_APPROVAL
        assert ex.step_results["notify"].status == StepStatus.PENDING

    @pytest.mark.asyncio
    async def test_gather_failure_is_non_fatal(self):
        registry = _mock_registry()
        registry.get_provider.return_value.get_current_alerts = AsyncMock(
            side_effect=RuntimeError("Datadog down")
        )
        rb = Runbook(
            name="Multi",
            steps=[
                RunbookStep(
                    id="gather",
                    action="gather",
                    description="gather",
                    integration="monitoring",
                    method="get_current_alerts",
                ),
                RunbookStep(
                    id="notify",
                    action="execute",
                    description="notify",
                    integration="communication",
                    method="send_message",
                    params={"channel": "c", "message": "m"},
                ),
            ],
        )
        executor = RunbookStepExecutor(registry=registry, ml_engine=_mock_ml())
        ex = await executor.execute_runbook(rb, _make_incident())
        # Gather failed but execution continued and completed
        assert ex.status == ExecutionStatus.COMPLETED
        assert ex.step_results["gather"].status == StepStatus.FAILED
        assert ex.step_results["notify"].status == StepStatus.SUCCESS
        # Failed gather stores empty result (does not block subsequent steps)
        assert ex.results["gather"] == {}

    @pytest.mark.asyncio
    async def test_execute_failure_is_fatal(self):
        registry = _mock_registry()
        registry.get_provider.return_value.restart_service = AsyncMock(
            side_effect=RuntimeError("Permission denied")
        )
        rb = Runbook(
            name="Multi",
            steps=[
                RunbookStep(
                    id="execute",
                    action="execute",
                    description="exec",
                    integration="compute",
                    method="restart_service",
                    params={"hostname": "h", "service": "s"},
                ),
                RunbookStep(
                    id="notify",
                    action="execute",
                    description="notify",
                    integration="communication",
                    method="send_message",
                    params={"channel": "c", "message": "m"},
                ),
            ],
        )
        executor = RunbookStepExecutor(registry=registry, ml_engine=_mock_ml())
        ex = await executor.execute_runbook(rb, _make_incident())
        assert ex.status == ExecutionStatus.FAILED
        assert ex.step_results["execute"].status == StepStatus.FAILED
        # Second step was never reached
        assert "notify" not in ex.step_results

    @pytest.mark.asyncio
    async def test_step_results_flow_into_template_params(self):
        """Verify results from step N feed {{ step_N.key }} in step N+1."""
        registry = _mock_registry()
        registry.get_provider.return_value.restart_service = AsyncMock(
            return_value={"status": "success"}
        )
        rb = Runbook(
            name="Chain",
            steps=[
                RunbookStep(
                    id="get_host",
                    action="gather",
                    description="get host",
                    integration="compute",
                    method="get_host_info",
                    params={"hostname": "{{ incident.metadata.host }}"},
                ),
                RunbookStep(
                    id="restart",
                    action="execute",
                    description="restart",
                    integration="compute",
                    method="restart_service",
                    params={
                        "hostname": "{{ get_host.hostname }}",
                        "service": "java",
                    },
                ),
            ],
        )
        executor = RunbookStepExecutor(registry=registry, ml_engine=_mock_ml())
        ex = await executor.execute_runbook(rb, _make_incident())
        assert ex.status == ExecutionStatus.COMPLETED
        # The restart call should have received the resolved hostname
        registry.get_provider.return_value.restart_service.assert_called_once_with(
            hostname="web-01", service="java"
        )

    @pytest.mark.asyncio
    async def test_empty_runbook_completes_immediately(self):
        executor = RunbookStepExecutor(registry=_mock_registry(), ml_engine=_mock_ml())
        rb = Runbook(name="Empty", steps=[])
        ex = await executor.execute_runbook(rb, _make_incident())
        assert ex.status == ExecutionStatus.COMPLETED
        assert ex.step_results == {}


# ---------------------------------------------------------------------------
# RunbookStepExecutor.resume_runbook
# ---------------------------------------------------------------------------


class TestResumeRunbook:
    @pytest.mark.asyncio
    async def test_resume_completes_execution(self):
        executor = RunbookStepExecutor(registry=_mock_registry(), ml_engine=_mock_ml())
        rb = _make_execute_runbook(requires_approval=True)
        incident = _make_incident()

        # First pass — should pause at approval gate
        ex = await executor.execute_runbook(rb, incident)
        assert ex.status == ExecutionStatus.AWAITING_APPROVAL

        # Resume with approval
        ex = await executor.resume_runbook(rb, incident, ex, approved_step_ids={"do_it"})
        assert ex.status == ExecutionStatus.COMPLETED
        assert ex.step_results["do_it"].status == StepStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_resume_noop_when_not_awaiting(self):
        executor = RunbookStepExecutor(registry=_mock_registry(), ml_engine=_mock_ml())
        rb = _make_gather_runbook()
        incident = _make_incident()

        ex = await executor.execute_runbook(rb, incident)
        assert ex.status == ExecutionStatus.COMPLETED

        # Calling resume on a completed execution is a no-op
        original_status = ex.status
        ex = await executor.resume_runbook(rb, incident, ex, approved_step_ids=set())
        assert ex.status == original_status

    @pytest.mark.asyncio
    async def test_resume_carries_prior_results(self):
        """Results from the first run should be available in resumed steps."""
        registry = _mock_registry()
        registry.get_provider.return_value.restart_service = AsyncMock(
            return_value={"status": "success"}
        )
        rb = Runbook(
            name="Carry",
            steps=[
                RunbookStep(
                    id="gather",
                    action="gather",
                    description="gather",
                    integration="compute",
                    method="get_host_info",
                    params={"hostname": "web-01"},
                ),
                RunbookStep(
                    id="execute",
                    action="execute",
                    description="exec",
                    integration="compute",
                    method="restart_service",
                    requires_approval=True,
                    params={
                        "hostname": "{{ gather.hostname }}",
                        "service": "java",
                    },
                ),
            ],
        )
        executor = RunbookStepExecutor(registry=registry, ml_engine=_mock_ml())
        incident = _make_incident()

        ex = await executor.execute_runbook(rb, incident)
        assert ex.status == ExecutionStatus.AWAITING_APPROVAL
        assert "gather" in ex.results  # first step ran

        ex = await executor.resume_runbook(rb, incident, ex, approved_step_ids={"execute"})
        assert ex.status == ExecutionStatus.COMPLETED
        # Template resolution used the carried-forward gather result
        registry.get_provider.return_value.restart_service.assert_called_once_with(
            hostname="web-01", service="java"
        )

    @pytest.mark.asyncio
    async def test_resume_stops_at_next_unapproved_gate(self):
        rb = Runbook(
            name="Two Gates",
            steps=[
                RunbookStep(
                    id="first",
                    action="execute",
                    description="first",
                    integration="compute",
                    method="restart_service",
                    requires_approval=True,
                    params={"hostname": "h", "service": "s"},
                ),
                RunbookStep(
                    id="second",
                    action="execute",
                    description="second",
                    integration="compute",
                    method="restart_service",
                    requires_approval=True,
                    params={"hostname": "h", "service": "s2"},
                ),
            ],
        )
        executor = RunbookStepExecutor(registry=_mock_registry(), ml_engine=_mock_ml())
        incident = _make_incident()

        ex = await executor.execute_runbook(rb, incident)
        assert ex.status == ExecutionStatus.AWAITING_APPROVAL

        # Approve only the first gate
        ex = await executor.resume_runbook(rb, incident, ex, approved_step_ids={"first"})
        assert ex.status == ExecutionStatus.AWAITING_APPROVAL
        assert ex.step_results["first"].status == StepStatus.SUCCESS
        assert ex.step_results["second"].status == StepStatus.PENDING_APPROVAL

        # Now approve the second gate
        ex = await executor.resume_runbook(rb, incident, ex, approved_step_ids={"second"})
        assert ex.status == ExecutionStatus.COMPLETED


# ---------------------------------------------------------------------------
# Timeline entries
# ---------------------------------------------------------------------------


class TestTimelineEntries:
    @pytest.mark.asyncio
    async def test_successful_step_adds_timeline_entry(self):
        executor = RunbookStepExecutor(registry=_mock_registry(), ml_engine=_mock_ml())
        rb = _make_gather_runbook()
        incident = _make_incident()
        initial_len = len(incident.timeline)

        await executor.execute_runbook(rb, incident)
        assert len(incident.timeline) == initial_len + 1
        entry = incident.timeline[-1]
        assert entry.event_type == "runbook_step_success"
        assert entry.source == "runbook_engine"
        assert "gather" in entry.details["step_id"]

    @pytest.mark.asyncio
    async def test_failed_step_adds_timeline_entry_with_error(self):
        registry = _mock_registry()
        registry.get_provider.return_value.get_current_alerts = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        executor = RunbookStepExecutor(registry=registry, ml_engine=_mock_ml())
        rb = _make_gather_runbook()
        incident = _make_incident()

        await executor.execute_runbook(rb, incident)
        entry = incident.timeline[-1]
        assert entry.event_type == "runbook_step_failed"
        assert entry.details["error"] == "boom"

    @pytest.mark.asyncio
    async def test_approval_gated_step_does_not_add_timeline_entry(self):
        """Steps that pause for approval are not executed, so no timeline entry."""
        executor = RunbookStepExecutor(registry=_mock_registry(), ml_engine=_mock_ml())
        rb = _make_execute_runbook(requires_approval=True)
        incident = _make_incident()
        initial_len = len(incident.timeline)

        await executor.execute_runbook(rb, incident)
        # No step was actually executed, so no new timeline entries
        assert len(incident.timeline) == initial_len

    @pytest.mark.asyncio
    async def test_multiple_steps_each_add_one_entry(self):
        rb = Runbook(
            name="Multi",
            steps=[
                RunbookStep(
                    id="g1",
                    action="gather",
                    description="g1",
                    integration="monitoring",
                    method="get_current_alerts",
                ),
                RunbookStep(
                    id="g2",
                    action="gather",
                    description="g2",
                    integration="monitoring",
                    method="get_logs",
                    params={"query": "error", "limit": 10},
                ),
            ],
        )
        executor = RunbookStepExecutor(registry=_mock_registry(), ml_engine=_mock_ml())
        incident = _make_incident()
        initial_len = len(incident.timeline)

        await executor.execute_runbook(rb, incident)
        assert len(incident.timeline) == initial_len + 2
