from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".agent"


def _load_agent_module(filename: str, module_name: str):
    module_path = AGENT_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module: {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


autopilot = _load_agent_module("autopilot.py", "tests.agent_autopilot")


def test_load_autopilot_config_reads_codex_settings():
    config = autopilot.load_autopilot_config()

    assert config.default_model == "gpt-5.4-mini"
    assert config.enable_subagents is True
    assert config.max_subagent_depth == 2
    assert config.enable_workflow_routing is True
    assert any(rule.group == "api_changes" for rule in config.trigger_rules)


def test_load_subagent_registry_reads_codex_profiles():
    registry = autopilot.load_subagent_registry()

    assert "api_contracts" in registry
    assert "test_planner" in registry
    assert registry["api_contracts"].path.endswith("api_contracts.toml")
    assert registry["api_contracts"].model == "gpt-5.4"


def test_validate_registry_returns_no_errors():
    errors = autopilot.validate_registry()

    assert errors == []


def test_classify_task_detects_contract_sensitive_flow():
    classification = autopilot.classify_task(
        "Update WebSocket payload and /result/{task_id} API response.",
        touched_files=[
            "src/routers/result.py",
            "frontend/src/api/interfaces.ts",
        ],
    )

    assert classification.task_type == "contract-sensitive"
    assert classification.risk_level == "high"
    assert classification.requires_orchestration is True
    assert "api-contract" in classification.labels
    assert "frontend-impact" in classification.labels
    assert classification.rule_matches


def test_classify_task_detects_local_low_risk_change():
    classification = autopilot.classify_task(
        "Update docs summary punctuation.",
        touched_files=["docs/ROADMAP.md"],
    )

    assert classification.task_type == "local-low-risk"
    assert classification.requires_orchestration is False


def test_build_execution_plan_selects_expected_subagents():
    plan = autopilot.build_execution_plan(
        "Investigate broken WebSocket status payload and keep interfaces.ts aligned.",
        touched_files=[
            "src/routers/websocket.py",
            "frontend/src/api/interfaces.ts",
            "tests/test_websocket_integration.py",
        ],
        urgency="high",
        depth="deep",
    )

    selected_names = [subagent.name for subagent in plan.subagents]

    assert plan.workflow == "contract_guard"
    assert "solution_designer" in selected_names
    assert "api_contracts" in selected_names
    assert "frontend_scout" in selected_names
    assert "test_planner" in selected_names
    assert "api_contracts" in plan.model_choices


def test_explain_plan_returns_routing_trace():
    plan = autopilot.build_execution_plan(
        "Compare API payload options and update frontend rendering.",
        touched_files=[
            "src/routers/result.py",
            "frontend/src/api/interfaces.ts",
        ],
        urgency="normal",
        depth="standard",
    )

    explanation = autopilot.explain_plan(plan)

    assert explanation["task_type"] == "contract-sensitive"
    assert explanation["selected_subagents"]
    assert explanation["rule_matches"]


def test_prepare_execution_requests_builds_runtime_payloads():
    plan = autopilot.build_execution_plan(
        "Compare API payload options and update frontend rendering.",
        touched_files=[
            "src/routers/result.py",
            "frontend/src/api/interfaces.ts",
        ],
        urgency="normal",
        depth="standard",
    )

    requests = autopilot.prepare_execution_requests(plan)

    assert requests
    assert requests[0].prompt
    assert requests[0].model
    assert requests[0].timeout_ms == 120000
    assert requests[0].metadata["workflow"] == plan.workflow


def test_codex_cli_adapter_builds_subprocess_invocation():
    plan = autopilot.build_execution_plan(
        "Compare API payload options and update frontend rendering.",
        touched_files=[
            "src/routers/result.py",
            "frontend/src/api/interfaces.ts",
        ],
    )
    request = autopilot.prepare_execution_requests(plan)[0]
    adapter = autopilot.CodexCliAdapter(binary_name="C:\\fake\\codex.exe")

    invocation = adapter.build_invocation(request)

    assert invocation.command[0].lower().endswith(("codex.cmd", "codex.exe"))
    assert "exec" in invocation.command
    assert "-m" in invocation.command
    assert "-s" in invocation.command
    assert "-C" in invocation.command
    assert invocation.command[-1] == "-"
    assert invocation.input_text == request.prompt
    assert invocation.timeout_ms == request.timeout_ms


@patch("tests.agent_autopilot.subprocess.run")
def test_codex_cli_adapter_executes_successful_process(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="done",
        stderr="",
    )
    adapter = autopilot.CodexCliAdapter(binary_name="C:\\fake\\codex.exe")
    request = autopilot.SubagentExecutionRequest(
        subagent_name="test_planner",
        prompt="hello",
        model="gpt-5.4-mini",
        reasoning_effort="medium",
        sandbox_mode="read-only",
        timeout_ms=1000,
        depth=1,
        metadata={},
    )

    result = adapter.execute([request])[0]

    assert result.status == "completed"
    assert result.output == "done"
    assert result.error is None
    assert result.failure is None


@patch("tests.agent_autopilot.subprocess.run")
def test_codex_cli_adapter_maps_nonzero_exit_to_failed_result(mock_run):
    mock_run.return_value = MagicMock(
        returncode=2,
        stdout="",
        stderr="boom",
    )
    adapter = autopilot.CodexCliAdapter(binary_name="C:\\fake\\codex.exe")
    request = autopilot.SubagentExecutionRequest(
        subagent_name="test_planner",
        prompt="hello",
        model="gpt-5.4-mini",
        reasoning_effort="medium",
        sandbox_mode="read-only",
        timeout_ms=1000,
        depth=1,
        metadata={},
    )

    result = adapter.execute([request])[0]

    assert result.status == "failed"
    assert result.error == "boom"
    assert result.failure is not None
    assert result.failure.code == autopilot.FailureCode.RUNTIME_EXIT_NONZERO


@patch("tests.agent_autopilot.subprocess.run")
@patch("tests.agent_autopilot._resolve_codex_binary_path")
def test_create_default_runtime_adapter_uses_codex_only(
    mock_resolve_binary,
    mock_run,
):
    mock_resolve_binary.return_value = "C:\\fake\\codex.exe"
    mock_run.return_value = MagicMock(returncode=0, stdout="0.1", stderr="")

    adapter = autopilot.create_default_runtime_adapter()

    assert isinstance(adapter, autopilot.CodexCliAdapter)
    assert adapter.resolved_binary == "C:\\fake\\codex.exe"


@patch("tests.agent_autopilot.subprocess.run")
@patch("tests.agent_autopilot._resolve_codex_binary_path")
def test_create_default_runtime_adapter_raises_with_probe_reason(
    mock_resolve_binary,
    mock_run,
):
    mock_resolve_binary.return_value = "C:\\fake\\codex.exe"
    mock_run.side_effect = PermissionError("Access denied")

    try:
        autopilot.create_default_runtime_adapter()
    except RuntimeError as exc:
        assert "not available" in str(exc)
        assert "Access denied" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected RuntimeError")


@patch("tests.agent_autopilot.subprocess.run")
@patch("tests.agent_autopilot._resolve_codex_binary_path")
def test_smoke_test_runtime_runs_only_probe_commands(
    mock_resolve_binary,
    mock_run,
):
    mock_resolve_binary.return_value = "C:\\fake\\codex.exe"
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="codex-cli 0.117.0", stderr=""),
        MagicMock(returncode=0, stdout="codex-cli 0.117.0", stderr=""),
        MagicMock(returncode=0, stdout="Run Codex non-interactively", stderr=""),
    ]

    result = autopilot.smoke_test_runtime()

    assert result.available is True
    assert result.error is None
    assert len(result.probes) == 2
    assert [probe.name for probe in result.probes] == ["version", "exec_help"]
    assert result.invocation_preview is not None
    assert result.invocation_preview["command"][-1] == "-"
    assert "env" not in result.invocation_preview


@patch("tests.agent_autopilot.subprocess.run")
@patch("tests.agent_autopilot._resolve_codex_binary_path")
def test_smoke_test_runtime_reports_probe_failure(
    mock_resolve_binary,
    mock_run,
):
    mock_resolve_binary.return_value = "C:\\fake\\codex.exe"
    mock_run.side_effect = PermissionError("Access denied")

    result = autopilot.smoke_test_runtime()

    assert result.available is False
    assert result.error is not None
    assert result.failure is not None
    assert result.failure.code == autopilot.FailureCode.RUNTIME_NOT_RUNNABLE
    assert len(result.probes) == 2
    assert all(probe.success is False for probe in result.probes)


@patch("tests.agent_autopilot.subprocess.run")
@patch("tests.agent_autopilot._resolve_codex_binary_path")
def test_exec_smoke_test_runtime_returns_success_on_expected_token(
    mock_resolve_binary,
    mock_run,
):
    mock_resolve_binary.return_value = "C:\\fake\\codex.exe"

    def run_side_effect(command, **kwargs):
        if "--version" in command:
            return MagicMock(returncode=0, stdout="codex-cli 0.117.0", stderr="")
        output_path = command[command.index("-o") + 1]
        Path(output_path).write_text("SMOKE_TEST_OK", encoding="utf-8")
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = run_side_effect

    result = autopilot.exec_smoke_test_runtime()

    assert result.success is True
    assert result.available is True
    assert result.stdout == "SMOKE_TEST_OK"
    assert result.returncode == 0
    assert "--ephemeral" in result.command_preview
    assert result.prompt_preview.startswith("Return exactly SMOKE_TEST_OK")
    assert result.failure is None


@patch("tests.agent_autopilot.build_execution_plan")
@patch("tests.agent_autopilot.subprocess.run")
@patch("tests.agent_autopilot._resolve_codex_binary_path")
def test_exec_smoke_test_runtime_does_not_use_planner(
    mock_resolve_binary,
    mock_run,
    mock_build_plan,
):
    mock_resolve_binary.return_value = "C:\\fake\\codex.exe"

    def run_side_effect(command, **kwargs):
        if "--version" in command:
            return MagicMock(returncode=0, stdout="codex-cli 0.117.0", stderr="")
        output_path = command[command.index("-o") + 1]
        Path(output_path).write_text("SMOKE_TEST_OK", encoding="utf-8")
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = run_side_effect

    result = autopilot.exec_smoke_test_runtime()

    mock_build_plan.assert_not_called()
    assert result.success is True


@patch("tests.agent_autopilot.subprocess.run")
@patch("tests.agent_autopilot._resolve_codex_binary_path")
def test_exec_smoke_test_runtime_rejects_unexpected_output(
    mock_resolve_binary,
    mock_run,
):
    mock_resolve_binary.return_value = "C:\\fake\\codex.exe"

    def run_side_effect(command, **kwargs):
        if "--version" in command:
            return MagicMock(returncode=0, stdout="codex-cli 0.117.0", stderr="")
        output_path = command[command.index("-o") + 1]
        Path(output_path).write_text("NOT_OK", encoding="utf-8")
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = run_side_effect

    result = autopilot.exec_smoke_test_runtime()

    assert result.success is False
    assert result.error == "unexpected smoke-test output"
    assert result.failure is not None
    assert result.failure.code == autopilot.FailureCode.UNEXPECTED_OUTPUT


@patch("tests.agent_autopilot.subprocess.run")
@patch("tests.agent_autopilot._resolve_codex_binary_path")
def test_exec_smoke_test_runtime_handles_timeout(
    mock_resolve_binary,
    mock_run,
):
    mock_resolve_binary.return_value = "C:\\fake\\codex.exe"
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="codex-cli 0.117.0", stderr=""),
        autopilot.subprocess.TimeoutExpired(cmd=["codex"], timeout=15),
    ]

    result = autopilot.exec_smoke_test_runtime()

    assert result.success is False
    assert result.error is not None
    assert "timeout" in result.error
    assert result.failure is not None
    assert result.failure.code == autopilot.FailureCode.RUNTIME_TIMEOUT


@patch("tests.agent_autopilot.subprocess.run")
@patch("tests.agent_autopilot._resolve_codex_binary_path")
def test_exec_smoke_test_runtime_falls_back_to_stdout_when_output_file_missing(
    mock_resolve_binary,
    mock_run,
):
    mock_resolve_binary.return_value = "C:\\fake\\codex.exe"

    def run_side_effect(command, **kwargs):
        if "--version" in command:
            return MagicMock(returncode=0, stdout="codex-cli 0.117.0", stderr="")
        return MagicMock(returncode=0, stdout="SMOKE_TEST_OK", stderr="")

    mock_run.side_effect = run_side_effect

    result = autopilot.exec_smoke_test_runtime()

    assert result.success is True
    assert result.stdout == "SMOKE_TEST_OK"
    assert result.failure is None


@patch("tests.agent_autopilot.subprocess.run")
@patch("tests.agent_autopilot._resolve_codex_binary_path")
def test_exec_smoke_test_runtime_reports_missing_output_when_empty(
    mock_resolve_binary,
    mock_run,
):
    mock_resolve_binary.return_value = "C:\\fake\\codex.exe"
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="codex-cli 0.117.0", stderr=""),
        MagicMock(returncode=0, stdout="", stderr=""),
    ]

    result = autopilot.exec_smoke_test_runtime()

    assert result.success is False
    assert result.error == "missing smoke-test output"
    assert result.failure is not None
    assert result.failure.code == autopilot.FailureCode.INVALID_STDOUT


@patch("tests.agent_autopilot.prepare_execution_requests")
@patch("tests.agent_autopilot.execute_plan")
@patch("tests.agent_autopilot.build_execution_plan")
@patch("tests.agent_autopilot.subprocess.run")
@patch("tests.agent_autopilot._resolve_codex_binary_path")
def test_mini_subagent_exec_test_returns_parsed_json_on_success(
    mock_resolve_binary,
    mock_run,
    mock_build_plan,
    mock_execute_plan,
    mock_prepare_requests,
):
    mock_resolve_binary.return_value = "C:\\fake\\codex.exe"

    def run_side_effect(command, **kwargs):
        if "--version" in command:
            return MagicMock(returncode=0, stdout="codex-cli 0.117.0", stderr="")
        output_path = command[command.index("-o") + 1]
        Path(output_path).write_text(
            json.dumps(
                {
                    "subagent": "test_planner",
                    "status": "ok",
                    "summary": "Smoke path is healthy",
                }
            ),
            encoding="utf-8",
        )
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = run_side_effect

    result = autopilot.mini_subagent_exec_test()

    mock_build_plan.assert_not_called()
    mock_execute_plan.assert_not_called()
    mock_prepare_requests.assert_not_called()
    assert result.success is True
    assert result.parsed_output is not None
    assert result.parsed_output["subagent"] == "test_planner"
    assert "--output-schema" in result.command_preview
    assert result.failure is None


@patch("tests.agent_autopilot.subprocess.run")
@patch("tests.agent_autopilot._resolve_codex_binary_path")
def test_mini_subagent_exec_test_rejects_invalid_json(
    mock_resolve_binary,
    mock_run,
):
    mock_resolve_binary.return_value = "C:\\fake\\codex.exe"

    def run_side_effect(command, **kwargs):
        if "--version" in command:
            return MagicMock(returncode=0, stdout="codex-cli 0.117.0", stderr="")
        output_path = command[command.index("-o") + 1]
        Path(output_path).write_text("not json", encoding="utf-8")
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = run_side_effect

    result = autopilot.mini_subagent_exec_test()

    assert result.success is False
    assert result.validation_error is not None
    assert result.error == "invalid json output"
    assert result.failure is not None
    assert result.failure.code == autopilot.FailureCode.INVALID_JSON


@patch("tests.agent_autopilot.subprocess.run")
@patch("tests.agent_autopilot._resolve_codex_binary_path")
def test_mini_subagent_exec_test_rejects_schema_mismatch(
    mock_resolve_binary,
    mock_run,
):
    mock_resolve_binary.return_value = "C:\\fake\\codex.exe"

    def run_side_effect(command, **kwargs):
        if "--version" in command:
            return MagicMock(returncode=0, stdout="codex-cli 0.117.0", stderr="")
        output_path = command[command.index("-o") + 1]
        Path(output_path).write_text(
            json.dumps(
                {
                    "subagent": "wrong_agent",
                    "status": "ok",
                    "summary": "Smoke path is healthy",
                }
            ),
            encoding="utf-8",
        )
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = run_side_effect

    result = autopilot.mini_subagent_exec_test()

    assert result.success is False
    assert result.validation_error == "json output subagent mismatch"
    assert result.error == "mini subagent output validation failed"
    assert result.failure is not None
    assert result.failure.code == autopilot.FailureCode.OUTPUT_SCHEMA_MISMATCH


@patch("tests.agent_autopilot.subprocess.run")
@patch("tests.agent_autopilot._resolve_codex_binary_path")
def test_mini_subagent_exec_test_handles_timeout(
    mock_resolve_binary,
    mock_run,
):
    mock_resolve_binary.return_value = "C:\\fake\\codex.exe"
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="codex-cli 0.117.0", stderr=""),
        autopilot.subprocess.TimeoutExpired(cmd=["codex"], timeout=20),
    ]

    result = autopilot.mini_subagent_exec_test()

    assert result.success is False
    assert result.error is not None
    assert "timeout" in result.error
    assert result.failure is not None
    assert result.failure.code == autopilot.FailureCode.RUNTIME_TIMEOUT


@patch("tests.agent_autopilot.subprocess.run")
@patch("tests.agent_autopilot._resolve_codex_binary_path")
def test_mini_subagent_exec_test_falls_back_to_stdout_when_output_file_missing(
    mock_resolve_binary,
    mock_run,
):
    mock_resolve_binary.return_value = "C:\\fake\\codex.exe"

    def run_side_effect(command, **kwargs):
        if "--version" in command:
            return MagicMock(returncode=0, stdout="codex-cli 0.117.0", stderr="")
        return MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "subagent": "test_planner",
                    "status": "ok",
                    "summary": "Healthy stdout fallback",
                }
            ),
            stderr="",
        )

    mock_run.side_effect = run_side_effect

    result = autopilot.mini_subagent_exec_test()

    assert result.success is True
    assert result.parsed_output is not None
    assert result.parsed_output["summary"] == "Healthy stdout fallback"
    assert result.failure is None


@patch("tests.agent_autopilot.subprocess.run")
@patch("tests.agent_autopilot._resolve_codex_binary_path")
def test_mini_subagent_exec_test_reports_missing_output_when_empty(
    mock_resolve_binary,
    mock_run,
):
    mock_resolve_binary.return_value = "C:\\fake\\codex.exe"
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="codex-cli 0.117.0", stderr=""),
        MagicMock(returncode=0, stdout="", stderr=""),
    ]

    result = autopilot.mini_subagent_exec_test()

    assert result.success is False
    assert result.error == "missing json output"
    assert result.validation_error == "missing json output"
    assert result.failure is not None
    assert result.failure.code == autopilot.FailureCode.INVALID_STDOUT


def test_build_real_exec_smoke_result_accepts_expected_token():
    result = autopilot._build_real_exec_smoke_result(
        resolved_binary="C:\\fake\\codex.exe",
        model="gpt-5.4-mini",
        sandbox_mode="read-only",
        command=["codex", "exec"],
        prompt="prompt",
        duration_ms=12,
        returncode=0,
        stdout="SMOKE_TEST_OK",
        stderr=None,
    )

    assert result.success is True
    assert result.stdout == "SMOKE_TEST_OK"
    assert result.failure is None


def test_build_mini_subagent_exec_result_accepts_valid_json_payload():
    result = autopilot._build_mini_subagent_exec_result(
        resolved_binary="C:\\fake\\codex.exe",
        request_payload={
            "subagent_name": "test_planner",
            "model": "gpt-5.4-mini",
            "sandbox_mode": "read-only",
            "timeout_ms": 20000,
        },
        command=["codex", "exec"],
        prompt="prompt",
        duration_ms=15,
        returncode=0,
        raw_stdout=None,
        raw_stderr=None,
        output_text=json.dumps(
            {
                "subagent": "test_planner",
                "status": "ok",
                "summary": "Structured output",
            }
        ),
    )

    assert result.success is True
    assert result.parsed_output == {
        "subagent": "test_planner",
        "status": "ok",
        "summary": "Structured output",
    }
    assert result.failure is None


@patch("tests.agent_autopilot.subprocess.run")
def test_run_runtime_probe_returns_typed_failure_on_missing_binary(mock_run):
    mock_run.side_effect = FileNotFoundError("missing")

    result = autopilot._run_runtime_probe("version", ["codex", "--version"])

    assert result.success is False
    assert result.failure is not None
    assert result.failure.code == autopilot.FailureCode.RUNTIME_NOT_FOUND


@patch("tests.agent_autopilot.subprocess.run")
def test_run_runtime_probe_returns_typed_failure_on_timeout(mock_run):
    mock_run.side_effect = autopilot.subprocess.TimeoutExpired(
        cmd=["codex", "--version"],
        timeout=5,
    )

    result = autopilot._run_runtime_probe("version", ["codex", "--version"])

    assert result.success is False
    assert result.failure is not None
    assert result.failure.code == autopilot.FailureCode.RUNTIME_TIMEOUT


@patch("tests.agent_autopilot.subprocess.run")
def test_run_runtime_probe_returns_typed_failure_on_nonzero_exit(mock_run):
    mock_run.return_value = MagicMock(returncode=9, stdout="", stderr="bad")

    result = autopilot._run_runtime_probe("version", ["codex", "--version"])

    assert result.success is False
    assert result.failure is not None
    assert result.failure.code == autopilot.FailureCode.RUNTIME_EXIT_NONZERO


def test_execution_failure_is_json_serializable():
    failure = autopilot.ExecutionFailure(
        code=autopilot.FailureCode.RUNTIME_TIMEOUT,
        stage=autopilot.FailureStage.EXECUTE_PROCESS,
        mode=autopilot.ExecutionMode.EXEC_SMOKE,
        message="timeout",
        retryable=True,
        details={"timeout_ms": 1000},
    )

    payload = failure.as_dict()

    assert payload["code"] == "runtime_timeout"
    assert payload["stage"] == "execute_process"
    assert payload["mode"] == "exec_smoke"
    assert json.loads(json.dumps(payload))["message"] == "timeout"


def test_execute_plan_runs_backend_and_collects_results():
    plan = autopilot.build_execution_plan(
        "Investigate WebSocket payload transitions.",
        touched_files=[
            "src/routers/websocket.py",
            "frontend/src/api/interfaces.ts",
        ],
        urgency="high",
        depth="deep",
    )

    def fake_executor(request):
        return autopilot.SubagentExecutionResult(
            subagent_name=request.subagent_name,
            status="completed",
            output=f"handled:{request.subagent_name}",
            metadata={"model": request.model},
        )

    backend = autopilot.CallableExecutionBackend(fake_executor)
    run = autopilot.execute_plan(
        plan,
        backend=backend,
        persist_outputs=False,
    )

    assert run.requests
    assert len(run.results) == len(run.requests)
    assert all(result.status == "completed" for result in run.results)
    assert run.execution_mode in {"parallel", "sequential"}


def test_dry_run_returns_json_serializable_structure():
    preview = autopilot.dry_run(
        "Investigate scoring regression for ratios and explainability.",
        touched_files=[
            "src/analysis/scoring.py",
            "src/tasks.py",
        ],
        urgency="normal",
        depth="standard",
    )

    assert preview["classification"]["task_type"] in autopilot.VALID_TASK_TYPES
    assert "synthesis" in preview
    assert "explain" in preview
    assert isinstance(preview["subagents"], list)
