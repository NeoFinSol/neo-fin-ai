from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Sequence


TASK_TYPE_TO_SUBAGENTS = {
    "local-low-risk": [],
    "cross-module": ["solution_designer", "test_planner"],
    "cross-layer": ["solution_designer", "test_planner"],
    "contract-sensitive": [
        "solution_designer",
        "api_contracts",
        "frontend_scout",
        "test_planner",
    ],
    "bug-investigation": [
        "debug_investigator",
        "solution_designer",
        "test_planner",
    ],
    "release/security-sensitive": [
        "solution_designer",
        "security_guardian",
        "devops_release",
        "test_planner",
    ],
}

VALID_TASK_TYPES = set(TASK_TYPE_TO_SUBAGENTS)

TRIGGER_GROUP_TO_LABEL = {
    "api_changes": "api-contract",
    "frontend_related": "frontend-impact",
    "persistence_related": "persistence-impact",
    "extraction": "extraction-impact",
    "scoring_related": "scoring-impact",
    "security_related": "security-impact",
    "release_related": "release-impact",
    "documentation_related": "documentation-impact",
}

WORKFLOW_BY_TASK_TYPE = {
    "local-low-risk": "local_fast_path",
    "cross-module": "focused_investigation",
    "cross-layer": "cross_layer_orchestration",
    "contract-sensitive": "contract_guard",
    "bug-investigation": "bug_hunt",
    "release/security-sensitive": "release_guard",
}

LAYER_PATTERNS = (
    ("frontend", re.compile(r"^frontend/")),
    ("routers", re.compile(r"^src/routers/")),
    ("tasks", re.compile(r"^src/tasks\.py$")),
    ("analysis", re.compile(r"^src/analysis/")),
    ("core", re.compile(r"^src/core/")),
    ("db", re.compile(r"^src/db/")),
    ("docs", re.compile(r"^(docs/|\.agent/|\.codex/)")),
    ("tests", re.compile(r"^tests/")),
)

REAL_EXEC_SMOKE_TOKEN = "SMOKE_TEST_OK"
REAL_EXEC_SMOKE_MAX_OUTPUT_CHARS = 64
REAL_EXEC_SMOKE_TIMEOUT_MS = 15000
MINI_SUBAGENT_EXEC_TIMEOUT_MS = 20000
MINI_SUBAGENT_SUMMARY_MAX_CHARS = 120
SUBAGENT_FINAL_OUTPUT_CONTRACT = "subagent_final_v1"
SUBAGENT_FINAL_OUTPUT_STATUS = "ok"
SUBAGENT_FINAL_SUMMARY_MAX_CHARS = 400
SUBAGENT_FINAL_OUTPUT_FIELDS = (
    "subagent",
    "status",
    "summary",
    "findings",
    "risks",
    "files_to_change",
)


@dataclass(frozen=True)
class TriggerRule:
    group: str
    label: str
    keywords: tuple[str, ...]


class FailureCode(str, Enum):
    RUNTIME_NOT_FOUND = "runtime_not_found"
    RUNTIME_NOT_RUNNABLE = "runtime_not_runnable"
    RUNTIME_TIMEOUT = "runtime_timeout"
    RUNTIME_EXIT_NONZERO = "runtime_exit_nonzero"
    INVALID_STDOUT = "invalid_stdout"
    INVALID_JSON = "invalid_json"
    OUTPUT_SCHEMA_MISMATCH = "output_schema_mismatch"
    UNEXPECTED_OUTPUT = "unexpected_output"
    CONFIG_ERROR = "config_error"
    INTERNAL_ERROR = "internal_error"


class FailureStage(str, Enum):
    RESOLVE_RUNTIME = "resolve_runtime"
    PROBE_RUNTIME = "probe_runtime"
    BUILD_INVOCATION = "build_invocation"
    EXECUTE_PROCESS = "execute_process"
    PARSE_OUTPUT = "parse_output"
    VALIDATE_OUTPUT = "validate_output"
    PREPARE_REQUEST = "prepare_request"


class ExecutionMode(str, Enum):
    RUNTIME_SMOKE = "runtime_smoke"
    EXEC_SMOKE = "exec_smoke"
    MINI_SUBAGENT_EXEC = "mini_subagent_exec"
    SUBPROCESS_BACKEND = "subprocess_backend"


@dataclass(frozen=True)
class ExecutionFailure:
    code: FailureCode
    stage: FailureStage
    mode: ExecutionMode
    message: str
    retryable: bool
    details: dict[str, object] | None = None

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["code"] = self.code.value
        payload["stage"] = self.stage.value
        payload["mode"] = self.mode.value
        return payload


@dataclass(frozen=True)
class AutopilotConfig:
    default_model: str
    low_risk_model: str
    high_risk_model: str
    deep_analysis_model: str
    code_agent_model: str
    trigger_rules: tuple[TriggerRule, ...]
    subagent_model_overrides: dict[str, str]
    limits: dict[str, object]
    enable_subagents: bool
    max_subagent_depth: int
    subagent_timeout_ms: int
    save_subagent_responses: bool
    log_directory: str
    enable_workflow_routing: bool
    use_parallel_subagents: bool
    use_trigger_routing: bool


@dataclass(frozen=True)
class SubagentSpec:
    name: str
    path: str
    description: str
    model: str
    reasoning_effort: str
    sandbox_mode: str | None
    developer_instructions: str | None
    nickname_candidates: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RuleMatch:
    source: str
    value: str
    matched_by: str
    label: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass(frozen=True)
class TaskClassification:
    task_type: str
    risk_level: str
    labels: list[str]
    reasons: list[str]
    touched_files: list[str]
    touched_layers: list[str]
    requires_orchestration: bool
    rule_matches: list[RuleMatch]

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["rule_matches"] = [item.as_dict() for item in self.rule_matches]
        return payload


@dataclass(frozen=True)
class SubagentRequest:
    name: str
    purpose: str
    priority: int
    reasoning: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PlannedModelChoice:
    subagent_name: str
    model: str
    reasoning_effort: str
    justification: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class SynthesisSkeleton:
    touched_files: list[str]
    invariants: list[str]
    risks: list[str]
    safe_path: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionPlan:
    task_text: str
    workflow: str
    classification: TaskClassification
    subagents: list[SubagentRequest]
    model_choices: dict[str, PlannedModelChoice]
    synthesis: SynthesisSkeleton

    def as_dict(self) -> dict[str, object]:
        return {
            "task_text": self.task_text,
            "workflow": self.workflow,
            "classification": self.classification.as_dict(),
            "subagents": [item.as_dict() for item in self.subagents],
            "model_choices": {
                name: choice.as_dict()
                for name, choice in self.model_choices.items()
            },
            "synthesis": self.synthesis.as_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, indent=2)


@dataclass(frozen=True)
class SubagentExecutionRequest:
    subagent_name: str
    prompt: str
    model: str
    reasoning_effort: str
    sandbox_mode: str | None
    timeout_ms: int
    depth: int
    metadata: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SubagentFinalOutput:
    subagent: str
    status: str
    summary: str
    findings: list[str]
    risks: list[str]
    files_to_change: list[str]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SubagentExecutionResult:
    subagent_name: str
    status: str
    output: str | None = None
    final_output: SubagentFinalOutput | None = None
    error: str | None = None
    duration_ms: int | None = None
    metadata: dict[str, object] | None = None
    failure: ExecutionFailure | None = None

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["final_output"] = (
            self.final_output.as_dict() if self.final_output else None
        )
        payload["failure"] = (
            self.failure.as_dict() if self.failure else None
        )
        return payload


@dataclass(frozen=True)
class ExecutionRun:
    plan: ExecutionPlan
    requests: list[SubagentExecutionRequest]
    results: list[SubagentExecutionResult]
    execution_mode: str

    def as_dict(self) -> dict[str, object]:
        return {
            "plan": self.plan.as_dict(),
            "requests": [request.as_dict() for request in self.requests],
            "results": [result.as_dict() for result in self.results],
            "execution_mode": self.execution_mode,
        }


@dataclass(frozen=True)
class SubprocessInvocation:
    command: list[str]
    cwd: str
    env: dict[str, str]
    input_text: str
    timeout_ms: int
    output_contract: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeProbeResult:
    name: str
    command: list[str]
    success: bool
    returncode: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    error: str | None = None
    failure: ExecutionFailure | None = None

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["failure"] = (
            self.failure.as_dict() if self.failure else None
        )
        return payload


@dataclass(frozen=True)
class RuntimeSmokeTestResult:
    adapter_name: str
    resolved_binary: str | None
    available: bool
    invocation_preview: dict[str, object] | None
    probes: list[RuntimeProbeResult]
    error: str | None = None
    failure: ExecutionFailure | None = None

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["probes"] = [probe.as_dict() for probe in self.probes]
        payload["failure"] = (
            self.failure.as_dict() if self.failure else None
        )
        return payload


@dataclass(frozen=True)
class RuntimeExecSmokeTestResult:
    adapter_name: str
    resolved_binary: str | None
    model: str
    sandbox_mode: str
    available: bool
    command_preview: list[str]
    prompt_preview: str
    returncode: int | None = None
    duration_ms: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    success: bool = False
    error: str | None = None
    failure: ExecutionFailure | None = None

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["failure"] = (
            self.failure.as_dict() if self.failure else None
        )
        return payload


@dataclass(frozen=True)
class MiniSubagentExecTestResult:
    adapter_name: str
    resolved_binary: str | None
    request: dict[str, object]
    command_preview: list[str]
    prompt_preview: str
    success: bool
    returncode: int | None = None
    duration_ms: int | None = None
    raw_stdout: str | None = None
    raw_stderr: str | None = None
    parsed_output: dict[str, str] | None = None
    validation_error: str | None = None
    error: str | None = None
    failure: ExecutionFailure | None = None

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["failure"] = (
            self.failure.as_dict() if self.failure else None
        )
        return payload


@dataclass(frozen=True)
class DiagnosticExecContext:
    adapter_name: str
    resolved_binary: str | None
    selected_model: str
    availability_error: str | None


@dataclass(frozen=True)
class OneShotExecSnapshot:
    command: list[str]
    cwd: str
    output_file: str
    returncode: int | None = None
    duration_ms: int | None = None
    raw_stdout: str | None = None
    raw_stderr: str | None = None
    output_text: str | None = None
    error: str | None = None


def _normalize_dash_text(value: str) -> str:
    return (
        value.replace("\u2011", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
    )


def _normalize_model_name(model: str) -> str:
    return _normalize_dash_text(model).strip().lower()


def _normalize_reasoning_effort(value: str) -> str:
    normalized = _normalize_dash_text(value).strip().lower()
    if normalized == "very high":
        return "xhigh"
    return normalized


def _agent_dir() -> Path:
    return Path(__file__).resolve().parent


def _root_dir() -> Path:
    return _agent_dir().parent


def _default_codex_dir() -> Path:
    return _root_dir() / ".codex"


def _default_config_path() -> Path:
    return _default_codex_dir() / "config.toml"


def _default_agents_dir() -> Path:
    return _default_codex_dir() / "agents"


def _legacy_subagents_dir() -> Path:
    return _agent_dir() / "subagents"


def _read_toml(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _load_model_selector_module():
    module_name = "_neofin_choose_model_for_subagent"
    if module_name in sys.modules:
        return sys.modules[module_name]

    module_path = _agent_dir() / "choose_model_for_subagent.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Could not load model selector module: {module_path}"
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_autopilot_config(
    config_path: str | Path | None = None,
) -> AutopilotConfig:
    """Load autopilot routing config from .codex/config.toml."""

    path = Path(config_path) if config_path else _default_config_path()
    data = _read_toml(path)

    triggers = data.get("triggers", {})
    trigger_rules: list[TriggerRule] = []
    for group_name, keywords in triggers.items():
        label = TRIGGER_GROUP_TO_LABEL.get(group_name)
        if label is None:
            continue
        normalized_keywords = tuple(
            _normalize_dash_text(keyword).lower()
            for keyword in keywords
        )
        trigger_rules.append(
            TriggerRule(
                group=group_name,
                label=label,
                keywords=normalized_keywords,
            )
        )

    model_settings = data.get("model_settings", {})
    subagents = data.get("subagents", {})
    orchestration = data.get("orchestration", {})

    overrides = {
        key.removesuffix("_model"): _normalize_model_name(value)
        for key, value in subagents.items()
        if key.endswith("_model")
    }

    return AutopilotConfig(
        default_model=_normalize_model_name(
            data.get("default_model", "gpt-5.4-mini")
        ),
        low_risk_model=_normalize_model_name(
            model_settings.get("low_risk_model", "gpt-5.4-mini")
        ),
        high_risk_model=_normalize_model_name(
            model_settings.get("high_risk_model", "gpt-5.4")
        ),
        deep_analysis_model=_normalize_model_name(
            model_settings.get("deep_analysis_model", "gpt-5.3-codex")
        ),
        code_agent_model=_normalize_model_name(
            model_settings.get("code_agent_model", "gpt-5.3-codex")
        ),
        trigger_rules=tuple(trigger_rules),
        subagent_model_overrides=overrides,
        limits=data.get("limits", {}),
        enable_subagents=bool(data.get("enable_subagents", True)),
        max_subagent_depth=int(data.get("max_subagent_depth", 1)),
        subagent_timeout_ms=int(
            data.get("limits", {}).get("subagent_timeout_ms", 120000)
        ),
        save_subagent_responses=bool(
            data.get("logging", {}).get("save_subagent_responses", False)
        ),
        log_directory=str(
            data.get("logging", {}).get("log_directory", ".codex/logs/")
        ),
        enable_workflow_routing=bool(
            orchestration.get("enable_workflow_routing", True)
        ),
        use_parallel_subagents=bool(
            orchestration.get("use_parallel_subagents", True)
        ),
        use_trigger_routing=bool(
            orchestration.get("use_trigger_routing", True)
        ),
    )


def _legacy_markdown_description(subagent_name: str) -> str | None:
    path = _legacy_subagents_dir() / f"{subagent_name}.md"
    if not path.exists():
        return None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip().strip("`")
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue
        return line
    return None


def load_subagent_registry(
    agents_dir: str | Path | None = None,
) -> dict[str, SubagentSpec]:
    """Load the machine-readable subagent registry from .codex/agents."""

    base_dir = Path(agents_dir) if agents_dir else _default_agents_dir()
    registry: dict[str, SubagentSpec] = {}

    for path in sorted(base_dir.glob("*.toml")):
        data = _read_toml(path)
        description = data.get("description") or _legacy_markdown_description(
            path.stem
        )
        registry[path.stem] = SubagentSpec(
            name=path.stem,
            path=str(path),
            description=description or f"Profile loaded from {path.name}.",
            model=_normalize_model_name(data.get("model", "gpt-5.4-mini")),
            reasoning_effort=_normalize_reasoning_effort(
                data.get("model_reasoning_effort", "medium")
            ),
            sandbox_mode=data.get("sandbox_mode"),
            developer_instructions=data.get("developer_instructions"),
            nickname_candidates=tuple(data.get("nickname_candidates", [])),
        )
    return registry


def validate_registry(
    registry: dict[str, SubagentSpec] | None = None,
) -> list[str]:
    """Validate task mappings against the loaded registry."""

    loaded_registry = registry or load_subagent_registry()
    errors: list[str] = []

    for task_type, subagents in TASK_TYPE_TO_SUBAGENTS.items():
        for subagent_name in subagents:
            if subagent_name not in loaded_registry:
                errors.append(
                    f"{task_type} references missing subagent {subagent_name}"
                )
    return errors


def detect_layers(touched_files: Sequence[str] | None = None) -> list[str]:
    """Map touched files to coarse project layers."""

    layers: list[str] = []
    for raw_path in touched_files or []:
        normalized_path = raw_path.replace("\\", "/").lstrip("./")
        for layer_name, pattern in LAYER_PATTERNS:
            if pattern.search(normalized_path) and layer_name not in layers:
                layers.append(layer_name)
                break
    return layers


def _text_contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _derive_labels(
    task_text: str,
    touched_files: Sequence[str],
    config: AutopilotConfig,
) -> tuple[list[str], list[RuleMatch]]:
    normalized_text = task_text.lower()
    normalized_files = [
        path.replace("\\", "/").lower() for path in touched_files
    ]
    labels: list[str] = []
    rule_matches: list[RuleMatch] = []

    if config.use_trigger_routing:
        for rule in config.trigger_rules:
            for keyword in rule.keywords:
                if keyword in normalized_text:
                    if rule.label not in labels:
                        labels.append(rule.label)
                    rule_matches.append(
                        RuleMatch(
                            source="task_text",
                            value=keyword,
                            matched_by=rule.group,
                            label=rule.label,
                        )
                    )

    file_marker_map = {
        "frontend-impact": ("frontend/", "interfaces.ts"),
        "api-contract": ("/ws", "websocket", "result.py", "analyses.py"),
        "persistence-impact": ("/db/", "migration"),
        "extraction-impact": ("/analysis/pdf_", "/analysis/llm_extractor"),
        "scoring-impact": ("/analysis/scoring", "/analysis/ratios"),
        "documentation-impact": ("docs/", ".agent/", ".codex/"),
    }

    for label, markers in file_marker_map.items():
        for marker in markers:
            if any(marker in path for path in normalized_files):
                if label not in labels:
                    labels.append(label)
                rule_matches.append(
                    RuleMatch(
                        source="touched_files",
                        value=marker,
                        matched_by="path_marker",
                        label=label,
                    )
                )

    if _text_contains_any(normalized_text, ("release", "deploy", "runtime")):
        if "release-impact" not in labels:
            labels.append("release-impact")
        rule_matches.append(
            RuleMatch(
                source="task_text",
                value="release/runtime keyword",
                matched_by="derived_release_signal",
                label="release-impact",
            )
        )

    return labels, rule_matches


def classify_task(
    task_text: str,
    touched_files: Sequence[str] | None = None,
    *,
    config: AutopilotConfig | None = None,
) -> TaskClassification:
    """Classify a task using config-driven rules."""

    loaded_config = config or load_autopilot_config()
    files = list(touched_files or [])
    normalized_text = task_text.lower()
    layers = detect_layers(files)
    labels, rule_matches = _derive_labels(
        task_text,
        files,
        loaded_config,
    )
    reasons: list[str] = []

    task_type = "local-low-risk"
    risk_level = "low"

    security_terms = ("security", "auth", "secret", "deploy", "runtime")
    bug_terms = (
        "bug",
        "debug",
        "regression",
        "root cause",
        "investigate",
    )

    if _text_contains_any(normalized_text, security_terms):
        task_type = "release/security-sensitive"
        risk_level = "high"
        reasons.append("security or release keywords matched")
    elif _text_contains_any(normalized_text, bug_terms):
        task_type = "bug-investigation"
        risk_level = "medium"
        reasons.append("bug-investigation keywords matched")

    if (
        "api-contract" in labels
        and task_type != "release/security-sensitive"
    ):
        task_type = "contract-sensitive"
        risk_level = "high"
        reasons.append("API or WebSocket contract indicators matched")

    if len(layers) >= 2 and task_type not in {
        "contract-sensitive",
        "release/security-sensitive",
        "bug-investigation",
    }:
        task_type = "cross-layer"
        risk_level = "medium"
        reasons.append("multiple layers are touched")

    if task_type == "local-low-risk" and (
        len(files) >= 3 or (len(layers) == 1 and len(files) >= 2)
    ):
        task_type = "cross-module"
        risk_level = "medium"
        reasons.append("multiple files are touched within one area")

    if task_type == "local-low-risk":
        reasons.append("no high-risk triggers detected")

    if (
        "extraction-impact" in labels
        or "scoring-impact" in labels
        or "persistence-impact" in labels
    ) and risk_level != "high":
        risk_level = "medium"
        reasons.append("domain-critical area is involved")

    return TaskClassification(
        task_type=task_type,
        risk_level=risk_level,
        labels=labels,
        reasons=reasons,
        touched_files=files,
        touched_layers=layers,
        requires_orchestration=task_type != "local-low-risk",
        rule_matches=rule_matches,
    )


def select_workflow(classification: TaskClassification) -> str:
    """Select workflow for the current classification."""

    return WORKFLOW_BY_TASK_TYPE[classification.task_type]


def select_subagents(
    classification: TaskClassification,
    registry: dict[str, SubagentSpec],
) -> list[SubagentRequest]:
    """Build the requested subagent list for the classification."""

    ordered_names: list[str] = list(
        TASK_TYPE_TO_SUBAGENTS[classification.task_type]
    )
    label_to_subagent = {
        "api-contract": "api_contracts",
        "frontend-impact": "frontend_scout",
        "persistence-impact": "db_persistence",
        "extraction-impact": "extractor",
        "scoring-impact": "scoring_guardian",
        "security-impact": "security_guardian",
        "release-impact": "devops_release",
        "documentation-impact": "docs_keeper",
    }

    for label in classification.labels:
        subagent_name = label_to_subagent.get(label)
        if subagent_name and subagent_name not in ordered_names:
            ordered_names.append(subagent_name)

    subagents: list[SubagentRequest] = []
    for priority, subagent_name in enumerate(ordered_names, start=1):
        if subagent_name not in registry:
            continue
        subagents.append(
            SubagentRequest(
                name=subagent_name,
                purpose=registry[subagent_name].description,
                priority=priority,
                reasoning=f"selected_by={classification.task_type}",
            )
        )
    return subagents


def build_synthesis_skeleton(
    classification: TaskClassification,
) -> SynthesisSkeleton:
    """Create a structured synthesis template for the selected plan."""

    invariants = [
        "Preserve the layered architecture boundaries from AGENTS.md.",
    ]
    risks = [
        "Choose the smallest change-set that preserves current behaviour.",
    ]

    if "api-contract" in classification.labels:
        invariants.append(
            "Keep frontend/src/api/interfaces.ts aligned with payload changes."
        )
        risks.append(
            "Schema drift between backend responses and frontend consumers."
        )

    if "persistence-impact" in classification.labels:
        invariants.append("Keep SQL and commits confined to src/db/crud.py.")
        risks.append("History or JSON compatibility can silently regress.")

    if "extraction-impact" in classification.labels:
        invariants.append(
            "Preserve confidence metadata and fallback extraction semantics."
        )
        risks.append("OCR or fallback regressions may only appear on edge PDFs.")

    if "scoring-impact" in classification.labels:
        invariants.append("Keep ratios, scoring and explainability consistent.")
        risks.append("Score drift can break UI expectations without errors.")

    if (
        "security-impact" in classification.labels
        or "release-impact" in classification.labels
    ):
        invariants.append(
            "Do not weaken auth, upload or deployment safety guards."
        )
        risks.append(
            "Security-sensitive changes can fail only at runtime or deploy."
        )

    if classification.requires_orchestration:
        safe_path = (
            "Run read-only investigation with the selected subagents, then "
            "implement the smallest compatible change-set."
        )
    else:
        safe_path = (
            "Implement locally with targeted validation and no contract changes."
        )

    return SynthesisSkeleton(
        touched_files=classification.touched_files,
        invariants=invariants,
        risks=risks,
        safe_path=safe_path,
    )


def build_execution_plan(
    task_text: str,
    *,
    touched_files: Sequence[str] | None = None,
    urgency: str = "normal",
    depth: str = "standard",
    config_path: str | Path | None = None,
    agents_dir: str | Path | None = None,
) -> ExecutionPlan:
    """Build a full execution plan for the task."""

    config = load_autopilot_config(config_path)
    registry = load_subagent_registry(agents_dir)
    classification = classify_task(
        task_text,
        touched_files,
        config=config,
    )
    workflow = select_workflow(classification)
    subagent_requests = select_subagents(classification, registry)
    synthesis = build_synthesis_skeleton(classification)

    selector_module = _load_model_selector_module()
    chooser_config = selector_module.load_model_selection_config(config_path)
    agent_profiles = {
        name: selector_module.load_agent_model_profile(
            name,
            agents_dir=agents_dir,
        )
        for name in registry
    }

    model_choices: dict[str, PlannedModelChoice] = {}
    for subagent in subagent_requests:
        request = selector_module.ModelSelectionRequest(
            task_type=classification.task_type,
            risk_level=classification.risk_level,
            subagent_name=subagent.name,
            urgency=urgency,
            depth=depth,
        )
        selection = selector_module.choose_model_for_subagent(
            request,
            config=chooser_config,
            agent_profile=agent_profiles.get(subagent.name),
        )
        model_choices[subagent.name] = PlannedModelChoice(
            subagent_name=selection.subagent_name,
            model=selection.model,
            reasoning_effort=selection.reasoning_effort,
            justification=selection.justification,
        )

    return ExecutionPlan(
        task_text=task_text,
        workflow=workflow,
        classification=classification,
        subagents=subagent_requests,
        model_choices=model_choices,
        synthesis=synthesis,
    )


def explain_plan(plan: ExecutionPlan) -> dict[str, object]:
    """Return explainability details for a built plan."""

    return {
        "workflow": plan.workflow,
        "task_type": plan.classification.task_type,
        "risk_level": plan.classification.risk_level,
        "labels": plan.classification.labels,
        "reasons": plan.classification.reasons,
        "rule_matches": [
            match.as_dict() for match in plan.classification.rule_matches
        ],
        "selected_subagents": [item.name for item in plan.subagents],
    }


def build_subagent_prompt(
    plan: ExecutionPlan,
    subagent: SubagentRequest,
    *,
    spec: SubagentSpec,
) -> str:
    """Build the execution prompt for a single subagent."""

    touched_files = ", ".join(plan.classification.touched_files) or "(none)"
    labels = ", ".join(plan.classification.labels) or "(none)"
    reasons = "; ".join(plan.classification.reasons)
    invariants = "\n".join(f"- {item}" for item in plan.synthesis.invariants)
    risks = "\n".join(f"- {item}" for item in plan.synthesis.risks)

    sections = [
        f"Subagent: {subagent.name}",
        f"Purpose: {subagent.purpose}",
        f"Task: {plan.task_text}",
        f"Workflow: {plan.workflow}",
        f"Task type: {plan.classification.task_type}",
        f"Risk level: {plan.classification.risk_level}",
        f"Selection reason: {subagent.reasoning}",
        f"Detected labels: {labels}",
        f"Touched files: {touched_files}",
        f"Classification reasons: {reasons}",
        "Invariants:",
        invariants or "- Preserve current contracts.",
        "Risks:",
        risks or "- Keep changes minimal and safe.",
        "Safe path:",
        plan.synthesis.safe_path,
        "Expected output:",
        "Return exactly one JSON object and nothing else.",
        "The JSON must contain exactly these fields:",
        f'- "subagent": "{subagent.name}"',
        f'- "status": "{SUBAGENT_FINAL_OUTPUT_STATUS}"',
        '- "summary": non-empty string',
        '- "findings": list of strings',
        '- "risks": list of strings',
        '- "files_to_change": list of strings',
        "Do not wrap the JSON in markdown fences.",
        "Do not add extra keys.",
    ]

    if spec.developer_instructions:
        sections.extend(
            [
                "Subagent instructions:",
                spec.developer_instructions.strip(),
            ]
        )

    return "\n".join(sections)


def prepare_execution_requests(
    plan: ExecutionPlan,
    *,
    config: AutopilotConfig | None = None,
    registry: dict[str, SubagentSpec] | None = None,
    depth: int = 1,
) -> list[SubagentExecutionRequest]:
    """Build executable requests for the selected subagents."""

    loaded_config = config or load_autopilot_config()
    loaded_registry = registry or load_subagent_registry()

    if not loaded_config.enable_subagents:
        raise RuntimeError("Subagents are disabled in .codex/config.toml")

    if depth > loaded_config.max_subagent_depth:
        raise ValueError(
            "Requested depth exceeds max_subagent_depth from config"
        )

    requests: list[SubagentExecutionRequest] = []
    for subagent in plan.subagents:
        spec = loaded_registry[subagent.name]
        model_choice = plan.model_choices[subagent.name]
        prompt = build_subagent_prompt(plan, subagent, spec=spec)
        metadata = {
            "workflow": plan.workflow,
            "task_type": plan.classification.task_type,
            "risk_level": plan.classification.risk_level,
            "labels": plan.classification.labels,
            "priority": subagent.priority,
            "developer_instructions": spec.developer_instructions,
            "output_contract": SUBAGENT_FINAL_OUTPUT_CONTRACT,
        }
        requests.append(
            SubagentExecutionRequest(
                subagent_name=subagent.name,
                prompt=prompt,
                model=model_choice.model,
                reasoning_effort=model_choice.reasoning_effort,
                sandbox_mode=spec.sandbox_mode,
                timeout_ms=loaded_config.subagent_timeout_ms,
                depth=depth,
                metadata=metadata,
            )
        )
    return requests


class RuntimeAdapter:
    """Base adapter for concrete runtime integrations."""

    def __init__(
        self,
        executor,
        *,
        parallel: bool = False,
        max_workers: int | None = None,
    ) -> None:
        self._executor = executor
        self._parallel = parallel
        self._max_workers = max_workers

    def name(self) -> str:
        return self.__class__.__name__

    def is_available(self) -> bool:
        return True

    def execute(
        self,
        requests: Sequence[SubagentExecutionRequest],
    ) -> list[SubagentExecutionResult]:
        if not self._parallel or len(requests) <= 1:
            return [self._safe_execute(request) for request in requests]

        from concurrent.futures import ThreadPoolExecutor

        max_workers = self._max_workers or len(requests)
        results: list[SubagentExecutionResult] = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(self._safe_execute, request) for request in requests]
            for future in futures:
                results.append(future.result())
        return results

    def _safe_execute(
        self,
        request: SubagentExecutionRequest,
    ) -> SubagentExecutionResult:
        try:
            result = self._executor(request)
        except Exception as exc:  # pragma: no cover - defensive path
            return SubagentExecutionResult(
                subagent_name=request.subagent_name,
                status="failed",
                error=str(exc),
            )

        if isinstance(result, SubagentExecutionResult):
            return result

        if isinstance(result, dict):
            return SubagentExecutionResult(**result)

        return SubagentExecutionResult(
            subagent_name=request.subagent_name,
            status="completed",
            output=str(result),
        )


class CallableExecutionBackend(RuntimeAdapter):
    """Execution backend powered by a Python callable."""


class SubprocessRuntimeAdapter(RuntimeAdapter):
    """Base class for subprocess-backed concrete runtimes."""

    def __init__(
        self,
        binary_name: str,
        *,
        parallel: bool = False,
        max_workers: int | None = None,
    ) -> None:
        super().__init__(self._execute_one, parallel=parallel, max_workers=max_workers)
        self.binary_name = binary_name

    def is_available(self) -> bool:
        return shutil.which(self.binary_name) is not None

    def build_invocation(
        self,
        request: SubagentExecutionRequest,
    ) -> SubprocessInvocation:
        raise NotImplementedError

    def supports_output_contract(self) -> bool:
        return False

    def _execute_one(
        self,
        request: SubagentExecutionRequest,
    ) -> SubagentExecutionResult:
        invocation = self.build_invocation(request)
        command = list(invocation.command)
        output_contract = invocation.output_contract
        output_text: str | None = None
        started = time.perf_counter()
        try:
            if (
                output_contract == SUBAGENT_FINAL_OUTPUT_CONTRACT
                and self.supports_output_contract()
            ):
                with tempfile.TemporaryDirectory(prefix="codex-subagent-output-") as temp_dir:
                    schema_path = Path(temp_dir) / "output_schema.json"
                    output_path = Path(temp_dir) / "last_message.json"
                    _build_subagent_final_output_schema_file(
                        schema_path,
                        subagent_name=request.subagent_name,
                    )
                    command = _append_output_contract_args(
                        command,
                        schema_file=str(schema_path),
                        output_file=str(output_path),
                    )
                    completed = subprocess.run(
                        command,
                        input=invocation.input_text,
                        text=True,
                        capture_output=True,
                        cwd=invocation.cwd,
                        env=invocation.env,
                        timeout=max(invocation.timeout_ms / 1000, 1),
                        check=False,
                    )
                    output_text = _read_output_text(output_path)
            else:
                completed = subprocess.run(
                    command,
                    input=invocation.input_text,
                    text=True,
                    capture_output=True,
                    cwd=invocation.cwd,
                    env=invocation.env,
                    timeout=max(invocation.timeout_ms / 1000, 1),
                    check=False,
                )
        except (
            subprocess.TimeoutExpired,
            FileNotFoundError,
            PermissionError,
            OSError,
        ) as exc:
            failure = _failure_from_exception(
                exc,
                stage=FailureStage.EXECUTE_PROCESS,
                mode=ExecutionMode.SUBPROCESS_BACKEND,
                details={"subagent_name": request.subagent_name},
            )
            return SubagentExecutionResult(
                subagent_name=request.subagent_name,
                status="failed",
                error=failure.message,
                failure=failure,
            )

        duration_ms = int((time.perf_counter() - started) * 1000)
        stdout = _normalize_process_stream(completed.stdout)
        stderr = _normalize_process_stream(completed.stderr)

        if completed.returncode != 0:
            failure = _failure_from_returncode(
                returncode=completed.returncode,
                stderr=stderr,
                stage=FailureStage.EXECUTE_PROCESS,
                mode=ExecutionMode.SUBPROCESS_BACKEND,
                details={
                    "subagent_name": request.subagent_name,
                    "command": command,
                },
            )
            return SubagentExecutionResult(
                subagent_name=request.subagent_name,
                status="failed",
                output=stdout,
                error=failure.message,
                duration_ms=duration_ms,
                metadata={
                    "returncode": completed.returncode,
                    "command": command,
                },
                failure=failure,
            )

        if output_contract == SUBAGENT_FINAL_OUTPUT_CONTRACT:
            final_output, validation_error, error = _parse_subagent_final_output(
                output_text or stdout,
                expected_subagent=request.subagent_name,
            )
            if error:
                return SubagentExecutionResult(
                    subagent_name=request.subagent_name,
                    status="failed",
                    output=output_text or stdout,
                    error=error,
                    duration_ms=duration_ms,
                    metadata={
                        "returncode": completed.returncode,
                        "command": command,
                        "output_contract": output_contract,
                    },
                    failure=_build_one_shot_exec_failure(
                        mode=ExecutionMode.SUBPROCESS_BACKEND,
                        error=error,
                        returncode=completed.returncode,
                        validation_error=validation_error,
                        default_validation_code=FailureCode.OUTPUT_SCHEMA_MISMATCH,
                        details={
                            "subagent_name": request.subagent_name,
                            "returncode": completed.returncode,
                            "command": command,
                        },
                    ),
                )

            return SubagentExecutionResult(
                subagent_name=request.subagent_name,
                status="completed",
                output=output_text or stdout,
                final_output=final_output,
                error=stderr,
                duration_ms=duration_ms,
                metadata={
                    "returncode": completed.returncode,
                    "command": command,
                    "output_contract": output_contract,
                },
                failure=None,
            )

        return SubagentExecutionResult(
            subagent_name=request.subagent_name,
            status="completed",
            output=stdout,
            error=stderr,
            duration_ms=duration_ms,
            metadata={
                "returncode": completed.returncode,
                "command": command,
            },
            failure=None,
        )


def _resolve_codex_binary_path(
    explicit_binary: str | None = None,
) -> str | None:
    candidates: list[str] = []

    if explicit_binary:
        candidates.append(explicit_binary)

    env_binary = os.environ.get("CODEX_BINARY")
    if env_binary:
        candidates.append(env_binary)

    for binary_name in ("codex", "codex.exe"):
        resolved = shutil.which(binary_name)
        if resolved:
            candidates.append(resolved)

    windows_apps_root = Path("C:/Program Files/WindowsApps")
    if windows_apps_root.exists():
        for pattern in (
            "OpenAI.Codex_*/*/resources/codex.exe",
            "OpenAI.Codex_*/app/resources/codex.exe",
            "OpenAI.Codex_*/app/resources/codex",
        ):
            matches = sorted(
                windows_apps_root.glob(pattern),
                reverse=True,
            )
            for match in matches:
                candidates.append(str(match))

    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(Path(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        if Path(normalized).exists():
            return normalized

    return None


class CodexCliAdapter(SubprocessRuntimeAdapter):
    """Concrete runtime adapter backed by codex.exe."""

    def __init__(
        self,
        *,
        binary_name: str | None = None,
        parallel: bool = False,
        max_workers: int | None = None,
    ) -> None:
        resolved_binary = _resolve_codex_binary_path(binary_name)
        super().__init__(
            resolved_binary or binary_name or "codex",
            parallel=parallel,
            max_workers=max_workers,
        )
        self.resolved_binary = resolved_binary

    def supports_output_contract(self) -> bool:
        return True

    def availability_error(self) -> str | None:
        if not self.resolved_binary:
            return (
                "codex executable was not found via CODEX_BINARY, PATH, "
                "or WindowsApps installation paths"
            )
        try:
            subprocess.run(
                [self.resolved_binary, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except PermissionError as exc:
            return f"codex executable exists but is not runnable: {exc}"
        except OSError as exc:
            return f"codex runtime probe failed: {exc}"
        except subprocess.TimeoutExpired as exc:
            return f"codex runtime probe timed out: {exc}"
        return None

    def is_available(self) -> bool:
        return self.availability_error() is None

    def build_invocation(
        self,
        request: SubagentExecutionRequest,
    ) -> SubprocessInvocation:
        command_binary = self.resolved_binary or self.binary_name
        sandbox_mode = request.sandbox_mode or "read-only"
        command = [
            command_binary,
            "exec",
            "-m",
            request.model,
            "-s",
            sandbox_mode,
            "-C",
            str(_root_dir()),
            "-",
        ]
        env = os.environ.copy()
        return SubprocessInvocation(
            command=command,
            cwd=str(_root_dir()),
            env=env,
            input_text=request.prompt,
            timeout_ms=request.timeout_ms,
            output_contract=(
                str(request.metadata.get("output_contract"))
                if request.metadata.get("output_contract")
                else None
            ),
        )


def _write_execution_logs(
    results: Sequence[SubagentExecutionResult],
    *,
    config: AutopilotConfig,
) -> None:
    log_dir = _root_dir() / Path(config.log_directory)
    _ensure_directory(log_dir)

    for result in results:
        path = log_dir / f"{result.subagent_name}.json"
        payload = json.dumps(result.as_dict(), ensure_ascii=False, indent=2)
        path.write_text(payload, encoding="utf-8")


def _run_runtime_probe(
    name: str,
    command: Sequence[str],
    *,
    cwd: str | None = None,
    timeout_ms: int = 5000,
) -> RuntimeProbeResult:
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=max(timeout_ms / 1000, 1),
            check=False,
        )
    except (OSError, PermissionError, subprocess.TimeoutExpired) as exc:
        failure = _failure_from_exception(
            exc,
            stage=FailureStage.PROBE_RUNTIME,
            mode=ExecutionMode.RUNTIME_SMOKE,
            details={"probe": name, "command": list(command)},
        )
        return RuntimeProbeResult(
            name=name,
            command=list(command),
            success=False,
            error=failure.message,
            failure=failure,
        )

    stdout = completed.stdout.strip() or None
    stderr = completed.stderr.strip() or None
    failure = None
    error = None
    if completed.returncode != 0:
        failure = _failure_from_returncode(
            returncode=completed.returncode,
            stderr=stderr,
            stage=FailureStage.PROBE_RUNTIME,
            mode=ExecutionMode.RUNTIME_SMOKE,
            details={"probe": name, "command": list(command)},
        )
        error = failure.message
    return RuntimeProbeResult(
        name=name,
        command=list(command),
        success=completed.returncode == 0,
        returncode=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        error=error,
        failure=failure,
    )


def _serialize_invocation_preview(
    invocation: SubprocessInvocation,
) -> dict[str, object]:
    return {
        "command": invocation.command,
        "cwd": invocation.cwd,
        "input_text": invocation.input_text,
        "timeout_ms": invocation.timeout_ms,
    }


def _build_subagent_final_output_schema_payload(
    *,
    subagent_name: str,
) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(SUBAGENT_FINAL_OUTPUT_FIELDS),
        "properties": {
            "subagent": {
                "type": "string",
                "const": subagent_name,
            },
            "status": {
                "type": "string",
                "const": SUBAGENT_FINAL_OUTPUT_STATUS,
            },
            "summary": {
                "type": "string",
                "minLength": 1,
                "maxLength": SUBAGENT_FINAL_SUMMARY_MAX_CHARS,
            },
            "findings": {
                "type": "array",
                "items": {
                    "type": "string",
                    "minLength": 1,
                },
            },
            "risks": {
                "type": "array",
                "items": {
                    "type": "string",
                    "minLength": 1,
                },
            },
            "files_to_change": {
                "type": "array",
                "items": {
                    "type": "string",
                    "minLength": 1,
                },
            },
        },
    }


def _build_subagent_final_output_schema_file(
    path: Path,
    *,
    subagent_name: str,
) -> None:
    _write_json_file(
        path,
        _build_subagent_final_output_schema_payload(subagent_name=subagent_name),
    )


def _validate_string_list(
    payload: object,
    *,
    field_name: str,
) -> tuple[list[str] | None, str | None]:
    if not isinstance(payload, list):
        return None, f"{field_name} must be a list of non-empty strings"

    normalized: list[str] = []
    for item in payload:
        if not isinstance(item, str) or not item.strip():
            return None, f"{field_name} must be a list of non-empty strings"
        normalized.append(item.strip())
    return normalized, None


def _validate_subagent_final_output(
    payload: object,
    *,
    expected_subagent: str,
) -> str | None:
    if not isinstance(payload, dict):
        return "output must be a json object"

    if set(payload.keys()) != set(SUBAGENT_FINAL_OUTPUT_FIELDS):
        return (
            "json output must contain exactly "
            "subagent, status, summary, findings, risks, files_to_change"
        )

    if payload.get("subagent") != expected_subagent:
        return "json output subagent mismatch"

    if payload.get("status") != SUBAGENT_FINAL_OUTPUT_STATUS:
        return "json output status must be ok"

    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return "json output summary must be a non-empty string"

    if len(summary.strip()) > SUBAGENT_FINAL_SUMMARY_MAX_CHARS:
        return "json output summary is too long"

    for field_name in ("findings", "risks", "files_to_change"):
        _, error = _validate_string_list(payload.get(field_name), field_name=field_name)
        if error:
            return error

    return None


def _parse_subagent_final_output(
    output_text: str | None,
    *,
    expected_subagent: str,
) -> tuple[SubagentFinalOutput | None, str | None, str | None]:
    normalized = _normalize_json_candidate(output_text)
    if not normalized:
        return None, "missing json output", "missing json output"

    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError as exc:
        return None, f"invalid json: {exc.msg}", "invalid json output"

    validation_error = _validate_subagent_final_output(
        parsed,
        expected_subagent=expected_subagent,
    )
    if validation_error:
        return None, validation_error, "subagent output validation failed"

    findings, _ = _validate_string_list(parsed["findings"], field_name="findings")
    risks, _ = _validate_string_list(parsed["risks"], field_name="risks")
    files_to_change, _ = _validate_string_list(
        parsed["files_to_change"],
        field_name="files_to_change",
    )
    return (
        SubagentFinalOutput(
            subagent=str(parsed["subagent"]),
            status=str(parsed["status"]),
            summary=str(parsed["summary"]).strip(),
            findings=findings or [],
            risks=risks or [],
            files_to_change=files_to_change or [],
        ),
        None,
        None,
    )


def _real_exec_smoke_prompt() -> str:
    return (
        f"Return exactly {REAL_EXEC_SMOKE_TOKEN} and nothing else.\n"
        "Do not inspect files.\n"
        "Do not run commands.\n"
        "Do not modify files.\n"
        "Do not explain anything.\n"
        "Do not propose a plan."
    )


def _mini_subagent_exec_prompt(subagent_name: str) -> str:
    return (
        f'You are simulating subagent "{subagent_name}".\n'
        "Return exactly one JSON object and nothing else.\n"
        f'The JSON must be: {{"subagent":"{subagent_name}",'
        '"status":"ok","summary":"<short text>"}.\n'
        "Do not inspect files.\n"
        "Do not run commands.\n"
        "Do not modify files.\n"
        "Do not explain outside JSON."
    )


def _normalize_real_exec_smoke_output(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().strip('"').strip("'").strip()
    return normalized or None


def _normalize_json_candidate(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.startswith("```"):
        return None
    return normalized or None


def _make_failure(
    *,
    code: FailureCode,
    stage: FailureStage,
    mode: ExecutionMode,
    message: str,
    retryable: bool,
    details: dict[str, object] | None = None,
) -> ExecutionFailure:
    return ExecutionFailure(
        code=code,
        stage=stage,
        mode=mode,
        message=message,
        retryable=retryable,
        details=details,
    )


def _failure_from_exception(
    exc: Exception,
    *,
    stage: FailureStage,
    mode: ExecutionMode,
    details: dict[str, object] | None = None,
) -> ExecutionFailure:
    if isinstance(exc, FileNotFoundError):
        return _make_failure(
            code=FailureCode.RUNTIME_NOT_FOUND,
            stage=stage,
            mode=mode,
            message=f"runtime not found: {exc}",
            retryable=False,
            details=details,
        )
    if isinstance(exc, PermissionError):
        return _make_failure(
            code=FailureCode.RUNTIME_NOT_RUNNABLE,
            stage=stage,
            mode=mode,
            message=f"runtime permission error: {exc}",
            retryable=False,
            details=details,
        )
    if isinstance(exc, subprocess.TimeoutExpired):
        return _make_failure(
            code=FailureCode.RUNTIME_TIMEOUT,
            stage=stage,
            mode=mode,
            message=f"timeout: {exc}",
            retryable=True,
            details=details,
        )
    return _make_failure(
        code=FailureCode.INTERNAL_ERROR,
        stage=stage,
        mode=mode,
        message=str(exc),
        retryable=False,
        details=details,
    )


def _failure_from_returncode(
    *,
    returncode: int,
    stderr: str | None,
    stage: FailureStage,
    mode: ExecutionMode,
    details: dict[str, object] | None = None,
) -> ExecutionFailure:
    return _make_failure(
        code=FailureCode.RUNTIME_EXIT_NONZERO,
        stage=stage,
        mode=mode,
        message=stderr or f"exit code {returncode}",
        retryable=False,
        details={"returncode": returncode, **(details or {})},
    )


def _failure_from_validation(
    *,
    code: FailureCode,
    message: str,
    mode: ExecutionMode,
    details: dict[str, object] | None = None,
) -> ExecutionFailure:
    return _make_failure(
        code=code,
        stage=FailureStage.VALIDATE_OUTPUT,
        mode=mode,
        message=message,
        retryable=False,
        details=details,
    )


def _classify_exec_failure_code(
    *,
    error: str,
    returncode: int | None,
    default_validation_code: FailureCode,
) -> tuple[FailureCode, FailureStage]:
    normalized = error.lower()
    if "timeout" in normalized:
        return FailureCode.RUNTIME_TIMEOUT, FailureStage.EXECUTE_PROCESS
    if "runtime not found" in normalized:
        return FailureCode.RUNTIME_NOT_FOUND, FailureStage.EXECUTE_PROCESS
    if "runtime permission error" in normalized:
        return FailureCode.RUNTIME_NOT_RUNNABLE, FailureStage.EXECUTE_PROCESS
    if returncode is not None and returncode != 0:
        return FailureCode.RUNTIME_EXIT_NONZERO, FailureStage.EXECUTE_PROCESS
    if "invalid json" in normalized:
        return FailureCode.INVALID_JSON, FailureStage.VALIDATE_OUTPUT
    if "missing" in normalized:
        return FailureCode.INVALID_STDOUT, FailureStage.VALIDATE_OUTPUT
    return default_validation_code, FailureStage.VALIDATE_OUTPUT


def _prepare_diagnostic_exec_context(
    *,
    config: AutopilotConfig | None,
    binary_name: str | None,
    model: str | None,
) -> DiagnosticExecContext:
    loaded_config = config or load_autopilot_config()
    adapter = CodexCliAdapter(binary_name=binary_name)
    return DiagnosticExecContext(
        adapter_name=adapter.name(),
        resolved_binary=adapter.resolved_binary or adapter.binary_name,
        selected_model=model or loaded_config.low_risk_model or loaded_config.default_model,
        availability_error=adapter.availability_error(),
    )


def _build_runtime_unavailable_failure(
    *,
    mode: ExecutionMode,
    resolved_binary: str | None,
    error: str,
) -> ExecutionFailure:
    return _make_failure(
        code=FailureCode.RUNTIME_NOT_RUNNABLE,
        stage=FailureStage.PROBE_RUNTIME,
        mode=mode,
        message=error,
        retryable=False,
        details={"resolved_binary": resolved_binary},
    )


def _normalize_process_stream(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _read_output_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return _normalize_process_stream(path.read_text(encoding="utf-8"))


def _write_json_file(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_codex_exec_base_command(
    binary: str,
    *,
    model: str,
    sandbox_mode: str,
    cwd: str,
) -> list[str]:
    return [
        binary,
        "exec",
        "-m",
        model,
        "-s",
        sandbox_mode,
        "-C",
        cwd,
        "--skip-git-repo-check",
        "--ephemeral",
        "--color",
        "never",
    ]


def _build_one_shot_codex_exec_command(
    binary: str,
    *,
    model: str,
    sandbox_mode: str,
    cwd: str,
    output_file: str,
    extra_args: Sequence[str] = (),
) -> list[str]:
    command = _build_codex_exec_base_command(
        binary,
        model=model,
        sandbox_mode=sandbox_mode,
        cwd=cwd,
    )
    command.extend(extra_args)
    command.extend(
        [
            "-o",
            output_file,
            "-",
        ]
    )
    return command


def _append_output_contract_args(
    command: Sequence[str],
    *,
    schema_file: str,
    output_file: str,
) -> list[str]:
    updated = list(command)
    contract_args = ["--output-schema", schema_file, "-o", output_file]
    if updated and updated[-1] == "-":
        return updated[:-1] + contract_args + ["-"]
    return updated + contract_args


def _build_real_exec_smoke_command(
    binary: str,
    *,
    model: str,
    sandbox_mode: str,
    cwd: str,
    output_file: str,
) -> list[str]:
    return _build_one_shot_codex_exec_command(
        binary,
        model=model,
        sandbox_mode=sandbox_mode,
        cwd=cwd,
        output_file=output_file,
    )


def _build_output_schema_payload(
    *,
    subagent_name: str,
) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["subagent", "status", "summary"],
        "properties": {
            "subagent": {
                "type": "string",
                "const": subagent_name,
            },
            "status": {
                "type": "string",
                "const": "ok",
            },
            "summary": {
                "type": "string",
                "minLength": 1,
                "maxLength": MINI_SUBAGENT_SUMMARY_MAX_CHARS,
            },
        },
    }


def _build_output_schema_file(
    path: Path,
    *,
    subagent_name: str,
) -> None:
    _write_json_file(
        path,
        _build_output_schema_payload(subagent_name=subagent_name),
    )


def _build_mini_subagent_exec_command(
    binary: str,
    *,
    model: str,
    sandbox_mode: str,
    cwd: str,
    output_file: str,
    schema_file: str,
) -> list[str]:
    return _build_one_shot_codex_exec_command(
        binary,
        model=model,
        sandbox_mode=sandbox_mode,
        cwd=cwd,
        output_file=output_file,
        extra_args=("--output-schema", schema_file),
    )


def _build_mini_subagent_schema_file(cwd: str, subagent_name: str) -> str:
    schema_path = Path(cwd) / "output_schema.json"
    _build_output_schema_file(schema_path, subagent_name=subagent_name)
    return str(schema_path)


def _run_one_shot_codex_exec(
    *,
    resolved_binary: str,
    model: str,
    sandbox_mode: str,
    prompt: str,
    timeout_ms: int,
    temp_dir_prefix: str,
    build_command: Callable[[str, str, str], list[str]],
) -> OneShotExecSnapshot:
    with tempfile.TemporaryDirectory(prefix=temp_dir_prefix) as temp_dir:
        output_path = Path(temp_dir) / "last_message.txt"
        command = build_command(
            temp_dir,
            str(output_path),
            resolved_binary,
        )
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                cwd=temp_dir,
                env=os.environ.copy(),
                timeout=max(timeout_ms / 1000, 1),
                check=False,
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            return OneShotExecSnapshot(
                command=command,
                cwd=temp_dir,
                output_file=str(output_path),
                error=str(exc),
            )
        except subprocess.TimeoutExpired as exc:
            return OneShotExecSnapshot(
                command=command,
                cwd=temp_dir,
                output_file=str(output_path),
                error=f"timeout: {exc}",
            )

        return OneShotExecSnapshot(
            command=command,
            cwd=temp_dir,
            output_file=str(output_path),
            returncode=completed.returncode,
            duration_ms=int((time.perf_counter() - started) * 1000),
            raw_stdout=_normalize_process_stream(completed.stdout),
            raw_stderr=_normalize_process_stream(completed.stderr),
            output_text=_read_output_text(output_path),
        )


def smoke_test_runtime(
    *,
    config: AutopilotConfig | None = None,
    binary_name: str | None = None,
) -> RuntimeSmokeTestResult:
    """Run a no-cost Codex runtime smoke test without a real agent task."""

    loaded_config = config or load_autopilot_config()
    adapter = CodexCliAdapter(
        binary_name=binary_name,
        parallel=loaded_config.use_parallel_subagents,
    )
    resolved_binary = adapter.resolved_binary or adapter.binary_name
    error = adapter.availability_error()
    probes: list[RuntimeProbeResult] = []
    invocation_preview: dict[str, object] | None = None
    failure = None

    if resolved_binary:
        root_dir = str(_root_dir())
        probes.append(
            _run_runtime_probe(
                "version",
                [resolved_binary, "--version"],
                cwd=root_dir,
            )
        )
        probes.append(
            _run_runtime_probe(
                "exec_help",
                [resolved_binary, "exec", "--help"],
                cwd=root_dir,
            )
        )
        preview_request = SubagentExecutionRequest(
            subagent_name="smoke_test",
            prompt="Smoke test only. Do not run a real agent task.",
            model=loaded_config.default_model,
            reasoning_effort="low",
            sandbox_mode="read-only",
            timeout_ms=loaded_config.subagent_timeout_ms,
            depth=0,
            metadata={"purpose": "runtime_smoke_test"},
        )
        invocation_preview = _serialize_invocation_preview(
            adapter.build_invocation(preview_request)
        )
    elif error:
        failure = _make_failure(
            code=FailureCode.RUNTIME_NOT_FOUND,
            stage=FailureStage.RESOLVE_RUNTIME,
            mode=ExecutionMode.RUNTIME_SMOKE,
            message=error,
            retryable=False,
        )

    available = error is None and probes and all(probe.success for probe in probes)
    if error and failure is None:
        failure = _make_failure(
            code=FailureCode.RUNTIME_NOT_RUNNABLE,
            stage=FailureStage.PROBE_RUNTIME,
            mode=ExecutionMode.RUNTIME_SMOKE,
            message=error,
            retryable=False,
            details={"resolved_binary": resolved_binary},
        )
    return RuntimeSmokeTestResult(
        adapter_name=adapter.name(),
        resolved_binary=resolved_binary if resolved_binary else None,
        available=bool(available),
        invocation_preview=invocation_preview,
        probes=probes,
        error=error,
        failure=failure,
    )


def exec_smoke_test_runtime(
    *,
    config: AutopilotConfig | None = None,
    binary_name: str | None = None,
    model: str | None = None,
    sandbox_mode: str = "read-only",
    timeout_ms: int = REAL_EXEC_SMOKE_TIMEOUT_MS,
) -> RuntimeExecSmokeTestResult:
    """Run a single cheap real Codex exec smoke test."""

    context = _prepare_diagnostic_exec_context(
        config=config,
        binary_name=binary_name,
        model=model,
    )
    prompt = _real_exec_smoke_prompt()
    if context.availability_error:
        return RuntimeExecSmokeTestResult(
            adapter_name=context.adapter_name,
            resolved_binary=context.resolved_binary,
            model=context.selected_model,
            sandbox_mode=sandbox_mode,
            available=False,
            command_preview=[],
            prompt_preview=prompt,
            error=context.availability_error,
            failure=_build_runtime_unavailable_failure(
                mode=ExecutionMode.EXEC_SMOKE,
                resolved_binary=context.resolved_binary,
                error=context.availability_error,
            ),
        )

    return _run_real_exec_smoke(
        resolved_binary=str(context.resolved_binary),
        model=context.selected_model,
        sandbox_mode=sandbox_mode,
        prompt=prompt,
        timeout_ms=timeout_ms,
    )


def mini_subagent_exec_test(
    *,
    config: AutopilotConfig | None = None,
    binary_name: str | None = None,
    subagent_name: str = "test_planner",
    model: str | None = None,
    sandbox_mode: str = "read-only",
    timeout_ms: int = MINI_SUBAGENT_EXEC_TIMEOUT_MS,
) -> MiniSubagentExecTestResult:
    """Run one synthetic mini subagent exec without planner/orchestration."""

    context = _prepare_diagnostic_exec_context(
        config=config,
        binary_name=binary_name,
        model=model,
    )
    prompt = _mini_subagent_exec_prompt(subagent_name)
    request_payload = {
        "subagent_name": subagent_name,
        "model": context.selected_model,
        "sandbox_mode": sandbox_mode,
        "timeout_ms": timeout_ms,
    }
    if context.availability_error:
        return MiniSubagentExecTestResult(
            adapter_name=context.adapter_name,
            resolved_binary=context.resolved_binary,
            request=request_payload,
            command_preview=[],
            prompt_preview=prompt,
            success=False,
            validation_error=None,
            error=context.availability_error,
            failure=_build_runtime_unavailable_failure(
                mode=ExecutionMode.MINI_SUBAGENT_EXEC,
                resolved_binary=context.resolved_binary,
                error=context.availability_error,
            ),
        )

    return _run_mini_subagent_exec(
        resolved_binary=str(context.resolved_binary),
        request_payload=request_payload,
        prompt=prompt,
    )


def _run_real_exec_smoke(
    *,
    resolved_binary: str,
    model: str,
    sandbox_mode: str,
    prompt: str,
    timeout_ms: int,
) -> RuntimeExecSmokeTestResult:
    snapshot = _run_one_shot_codex_exec(
        resolved_binary=resolved_binary,
        model=model,
        sandbox_mode=sandbox_mode,
        prompt=prompt,
        timeout_ms=timeout_ms,
        temp_dir_prefix="codex-smoke-",
        build_command=lambda cwd, output_file, binary: _build_real_exec_smoke_command(
            binary,
            model=model,
            sandbox_mode=sandbox_mode,
            cwd=cwd,
            output_file=output_file,
        ),
    )
    if snapshot.error:
        return _real_exec_smoke_failure(
            resolved_binary=resolved_binary,
            model=model,
            sandbox_mode=sandbox_mode,
            command=snapshot.command,
            prompt=prompt,
            error=snapshot.error,
        )

    return _build_real_exec_smoke_result(
        resolved_binary=resolved_binary,
        model=model,
        sandbox_mode=sandbox_mode,
        command=snapshot.command,
        prompt=prompt,
        duration_ms=int(snapshot.duration_ms or 0),
        returncode=int(snapshot.returncode or 0),
        stdout=_normalize_real_exec_smoke_output(
            snapshot.output_text or snapshot.raw_stdout
        ),
        stderr=snapshot.raw_stderr,
    )


def _build_one_shot_exec_failure(
    *,
    mode: ExecutionMode,
    error: str,
    returncode: int | None,
    validation_error: str | None,
    default_validation_code: FailureCode,
    details: dict[str, object],
) -> ExecutionFailure:
    failure_code, failure_stage = _classify_exec_failure_code(
        error=error,
        returncode=returncode,
        default_validation_code=default_validation_code,
    )
    return _make_failure(
        code=failure_code,
        stage=failure_stage,
        mode=mode,
        message=validation_error or error,
        retryable=failure_code == FailureCode.RUNTIME_TIMEOUT,
        details=details,
    )


def _build_real_exec_smoke_result(
    *,
    resolved_binary: str,
    model: str,
    sandbox_mode: str,
    command: list[str],
    prompt: str,
    duration_ms: int,
    returncode: int,
    stdout: str | None,
    stderr: str | None,
) -> RuntimeExecSmokeTestResult:
    if returncode != 0:
        error = stderr or f"exit code {returncode}"
        return _real_exec_smoke_failure(
            resolved_binary=resolved_binary,
            model=model,
            sandbox_mode=sandbox_mode,
            command=command,
            prompt=prompt,
            returncode=returncode,
            duration_ms=duration_ms,
            stdout=stdout,
            stderr=stderr,
            error=error,
        )

    if not stdout:
        return _real_exec_smoke_failure(
            resolved_binary=resolved_binary,
            model=model,
            sandbox_mode=sandbox_mode,
            command=command,
            prompt=prompt,
            returncode=returncode,
            duration_ms=duration_ms,
            stderr=stderr,
            error="missing smoke-test output",
        )

    if len(stdout) > REAL_EXEC_SMOKE_MAX_OUTPUT_CHARS:
        return _real_exec_smoke_failure(
            resolved_binary=resolved_binary,
            model=model,
            sandbox_mode=sandbox_mode,
            command=command,
            prompt=prompt,
            returncode=returncode,
            duration_ms=duration_ms,
            stdout=stdout,
            stderr=stderr,
            error="unexpectedly long smoke-test output",
        )

    if stdout != REAL_EXEC_SMOKE_TOKEN:
        return _real_exec_smoke_failure(
            resolved_binary=resolved_binary,
            model=model,
            sandbox_mode=sandbox_mode,
            command=command,
            prompt=prompt,
            returncode=returncode,
            duration_ms=duration_ms,
            stdout=stdout,
            stderr=stderr,
            error="unexpected smoke-test output",
        )

    return RuntimeExecSmokeTestResult(
        adapter_name="CodexCliAdapter",
        resolved_binary=resolved_binary,
        model=model,
        sandbox_mode=sandbox_mode,
        available=True,
        command_preview=command,
        prompt_preview=prompt,
        returncode=returncode,
        duration_ms=duration_ms,
        stdout=stdout,
        stderr=stderr,
        success=True,
        error=None,
        failure=None,
    )


def _real_exec_smoke_failure(
    *,
    resolved_binary: str,
    model: str,
    sandbox_mode: str,
    command: list[str],
    prompt: str,
    error: str,
    returncode: int | None = None,
    duration_ms: int | None = None,
    stdout: str | None = None,
    stderr: str | None = None,
) -> RuntimeExecSmokeTestResult:
    return RuntimeExecSmokeTestResult(
        adapter_name="CodexCliAdapter",
        resolved_binary=resolved_binary,
        model=model,
        sandbox_mode=sandbox_mode,
        available=True,
        command_preview=command,
        prompt_preview=prompt,
        returncode=returncode,
        duration_ms=duration_ms,
        stdout=stdout,
        stderr=stderr,
        success=False,
        error=error,
        failure=_build_one_shot_exec_failure(
            mode=ExecutionMode.EXEC_SMOKE,
            error=error,
            returncode=returncode,
            validation_error=None,
            default_validation_code=FailureCode.UNEXPECTED_OUTPUT,
            details={
                "returncode": returncode,
                "command": command,
            },
        ),
    )


def _run_mini_subagent_exec(
    *,
    resolved_binary: str,
    request_payload: dict[str, object],
    prompt: str,
) -> MiniSubagentExecTestResult:
    subagent_name = str(request_payload["subagent_name"])
    model = str(request_payload["model"])
    sandbox_mode = str(request_payload["sandbox_mode"])
    timeout_ms = int(request_payload["timeout_ms"])
    snapshot = _run_one_shot_codex_exec(
        resolved_binary=resolved_binary,
        model=model,
        sandbox_mode=sandbox_mode,
        prompt=prompt,
        timeout_ms=timeout_ms,
        temp_dir_prefix="codex-mini-subagent-",
        build_command=lambda cwd, output_file, binary: _build_mini_subagent_exec_command(
            binary,
            model=model,
            sandbox_mode=sandbox_mode,
            cwd=cwd,
            output_file=output_file,
            schema_file=_build_mini_subagent_schema_file(cwd, subagent_name),
        ),
    )
    if snapshot.error:
        return _mini_subagent_exec_failure(
            resolved_binary=resolved_binary,
            request_payload=request_payload,
            command=snapshot.command,
            prompt=prompt,
            error=snapshot.error,
        )

    return _build_mini_subagent_exec_result(
        resolved_binary=resolved_binary,
        request_payload=request_payload,
        command=snapshot.command,
        prompt=prompt,
        duration_ms=int(snapshot.duration_ms or 0),
        returncode=int(snapshot.returncode or 0),
        raw_stdout=snapshot.raw_stdout,
        raw_stderr=snapshot.raw_stderr,
        output_text=_normalize_json_candidate(
            snapshot.output_text or snapshot.raw_stdout
        ),
    )


def _build_mini_subagent_exec_result(
    *,
    resolved_binary: str,
    request_payload: dict[str, object],
    command: list[str],
    prompt: str,
    duration_ms: int,
    returncode: int,
    raw_stdout: str | None,
    raw_stderr: str | None,
    output_text: str | None,
) -> MiniSubagentExecTestResult:
    if returncode != 0:
        error = raw_stderr or f"exit code {returncode}"
        return _mini_subagent_exec_failure(
            resolved_binary=resolved_binary,
            request_payload=request_payload,
            command=command,
            prompt=prompt,
            returncode=returncode,
            duration_ms=duration_ms,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            error=error,
        )

    if not output_text:
        return _mini_subagent_exec_failure(
            resolved_binary=resolved_binary,
            request_payload=request_payload,
            command=command,
            prompt=prompt,
            returncode=returncode,
            duration_ms=duration_ms,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            validation_error="missing json output",
            error="missing json output",
        )

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        return _mini_subagent_exec_failure(
            resolved_binary=resolved_binary,
            request_payload=request_payload,
            command=command,
            prompt=prompt,
            returncode=returncode,
            duration_ms=duration_ms,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            validation_error=f"invalid json: {exc.msg}",
            error="invalid json output",
        )

    validation_error = _validate_mini_subagent_output(
        parsed,
        expected_subagent=str(request_payload["subagent_name"]),
    )
    if validation_error:
        return _mini_subagent_exec_failure(
            resolved_binary=resolved_binary,
            request_payload=request_payload,
            command=command,
            prompt=prompt,
            returncode=returncode,
            duration_ms=duration_ms,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            parsed_output=parsed if isinstance(parsed, dict) else None,
            validation_error=validation_error,
            error="mini subagent output validation failed",
        )

    parsed_output = {
        "subagent": str(parsed["subagent"]),
        "status": str(parsed["status"]),
        "summary": str(parsed["summary"]).strip(),
    }
    return MiniSubagentExecTestResult(
        adapter_name="CodexCliAdapter",
        resolved_binary=resolved_binary,
        request=request_payload,
        command_preview=command,
        prompt_preview=prompt,
        success=True,
        returncode=returncode,
        duration_ms=duration_ms,
        raw_stdout=raw_stdout,
        raw_stderr=raw_stderr,
        parsed_output=parsed_output,
        validation_error=None,
        error=None,
    )


def _validate_mini_subagent_output(
    payload: object,
    *,
    expected_subagent: str,
) -> str | None:
    if not isinstance(payload, dict):
        return "output must be a json object"

    expected_keys = {"subagent", "status", "summary"}
    if set(payload.keys()) != expected_keys:
        return "json output must contain exactly subagent, status, summary"

    if payload.get("subagent") != expected_subagent:
        return "json output subagent mismatch"

    if payload.get("status") != "ok":
        return "json output status must be ok"

    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return "json output summary must be a non-empty string"

    if len(summary.strip()) > MINI_SUBAGENT_SUMMARY_MAX_CHARS:
        return "json output summary is too long"

    return None


def _mini_subagent_exec_failure(
    *,
    resolved_binary: str,
    request_payload: dict[str, object],
    command: list[str],
    prompt: str,
    error: str,
    returncode: int | None = None,
    duration_ms: int | None = None,
    raw_stdout: str | None = None,
    raw_stderr: str | None = None,
    parsed_output: dict[str, object] | None = None,
    validation_error: str | None = None,
) -> MiniSubagentExecTestResult:
    normalized_parsed = None
    if isinstance(parsed_output, dict):
        normalized_parsed = {
            str(key): str(value)
            for key, value in parsed_output.items()
        }
    return MiniSubagentExecTestResult(
        adapter_name="CodexCliAdapter",
        resolved_binary=resolved_binary,
        request=request_payload,
        command_preview=command,
        prompt_preview=prompt,
        success=False,
        returncode=returncode,
        duration_ms=duration_ms,
        raw_stdout=raw_stdout,
        raw_stderr=raw_stderr,
        parsed_output=normalized_parsed,
        validation_error=validation_error,
        error=error,
        failure=_build_one_shot_exec_failure(
            mode=ExecutionMode.MINI_SUBAGENT_EXEC,
            error=error,
            returncode=returncode,
            validation_error=validation_error,
            default_validation_code=FailureCode.OUTPUT_SCHEMA_MISMATCH
            if validation_error
            else FailureCode.UNEXPECTED_OUTPUT,
            details={
                "returncode": returncode,
                "command": command,
            },
        ),
    )


def create_default_runtime_adapter(
    config: AutopilotConfig | None = None,
) -> RuntimeAdapter:
    """Create the default Codex runtime adapter."""

    loaded_config = config or load_autopilot_config()
    parallel = loaded_config.use_parallel_subagents
    codex_adapter = CodexCliAdapter(parallel=parallel)
    if codex_adapter.is_available():
        return codex_adapter

    error = codex_adapter.availability_error() or "unknown runtime error"
    raise RuntimeError(f"Codex runtime adapter is not available: {error}")


def execute_plan(
    plan: ExecutionPlan,
    *,
    backend: RuntimeAdapter,
    config: AutopilotConfig | None = None,
    registry: dict[str, SubagentSpec] | None = None,
    depth: int = 1,
    persist_outputs: bool | None = None,
) -> ExecutionRun:
    """Execute the selected subagents using the provided backend."""

    loaded_config = config or load_autopilot_config()
    loaded_registry = registry or load_subagent_registry()
    requests = prepare_execution_requests(
        plan,
        config=loaded_config,
        registry=loaded_registry,
        depth=depth,
    )
    results = backend.execute(requests)

    should_persist = (
        loaded_config.save_subagent_responses
        if persist_outputs is None
        else persist_outputs
    )
    if should_persist:
        _write_execution_logs(results, config=loaded_config)

    execution_mode = (
        "parallel"
        if loaded_config.use_parallel_subagents and len(requests) > 1
        else "sequential"
    )
    return ExecutionRun(
        plan=plan,
        requests=requests,
        results=results,
        execution_mode=execution_mode,
    )


def dry_run(
    task_text: str,
    *,
    touched_files: Sequence[str] | None = None,
    urgency: str = "normal",
    depth: str = "standard",
    config_path: str | Path | None = None,
    agents_dir: str | Path | None = None,
) -> dict[str, object]:
    """Return a JSON-serializable preview of the execution plan."""

    plan = build_execution_plan(
        task_text,
        touched_files=touched_files,
        urgency=urgency,
        depth=depth,
        config_path=config_path,
        agents_dir=agents_dir,
    )
    payload = plan.as_dict()
    payload["explain"] = explain_plan(plan)
    return payload


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="NeoFin AI autopilot dry-run helper"
    )
    parser.add_argument(
        "task",
        nargs="?",
        help="Task description to classify and plan",
    )
    parser.add_argument(
        "--file",
        dest="touched_files",
        action="append",
        default=[],
        help="Touched file path. May be passed multiple times.",
    )
    parser.add_argument(
        "--urgency",
        choices=("normal", "high", "critical"),
        default="normal",
        help="Urgency level for model selection",
    )
    parser.add_argument(
        "--depth",
        choices=("shallow", "standard", "deep"),
        default="standard",
        help="Expected investigation depth for model selection",
    )
    parser.add_argument(
        "--smoke-test-runtime",
        action="store_true",
        help="Run a no-cost Codex runtime smoke test and exit",
    )
    parser.add_argument(
        "--smoke-test-real-exec",
        action="store_true",
        help="Run a single cheap real Codex exec smoke test and exit",
    )
    parser.add_argument(
        "--mini-subagent-exec-test",
        action="store_true",
        help="Run one synthetic mini subagent exec test and exit",
    )
    args = parser.parse_args()

    if args.smoke_test_runtime:
        print(
            json.dumps(
                smoke_test_runtime().as_dict(),
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(0)

    if args.smoke_test_real_exec:
        print(
            json.dumps(
                exec_smoke_test_runtime().as_dict(),
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(0)

    if args.mini_subagent_exec_test:
        print(
            json.dumps(
                mini_subagent_exec_test().as_dict(),
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(0)

    if not args.task:
        parser.error(
            "task is required unless a smoke-test flag is used"
        )

    plan = build_execution_plan(
        args.task,
        touched_files=args.touched_files,
        urgency=args.urgency,
        depth=args.depth,
    )
    print(plan.to_json())
