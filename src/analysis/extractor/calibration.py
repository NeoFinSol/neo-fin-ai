from __future__ import annotations

import copy
import hashlib
import json
import logging
import warnings
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Final

from .confidence_policy import ConfidencePolicy
from .pipeline import build_extractor_trace, build_metadata_from_trace
from .ranking import apply_confidence_filter, build_metadata_from_candidate
from .runtime_decisions import should_prefer_llm_metric
from .types import ExtractionMetadata, RawMetricCandidate

DEFAULT_MANIFEST_PATH: Final = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "data"
    / "extractor_confidence_calibration"
)
DEFAULT_FIXTURE_MANIFEST_PATH: Final = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "data"
    / "pdf_real_fixtures"
    / "manifest.json"
)
SWEEP_OFFSETS: Final[tuple[float, ...]] = (-0.10, -0.05, 0.0, 0.05, 0.10)
SOURCE_STRICTNESS_VALUES: Final[tuple[str, ...]] = (
    "unspecified",
    "advisory",
    "critical",
)
SUITE_TIERS: Final[tuple[str, ...]] = ("fast", "gated")
REQUIRED_DECISION_SURFACES: Final[tuple[str, ...]] = (
    "threshold_boundary",
    "winner_selection",
    "merge_replacement",
    "expected_absent",
)
EXPANSION_PRIORITY_SURFACES: Final[tuple[str, ...]] = (
    "threshold_survival",
    "authoritative_override",
    "approximation_separation",
)
DECISION_SURFACES: Final[tuple[str, ...]] = (
    *REQUIRED_DECISION_SURFACES,
    *EXPANSION_PRIORITY_SURFACES,
)
RISK_TAG_VOCABULARY: Final[tuple[str, ...]] = (
    "historically_flaky",
    "ocr_fragile",
    "low_confidence",
    "source_sensitive",
    "replacement_path",
    "false_positive_trap",
    "boundary_near_0_5",
    "weak_keyword",
    "weak_ocr_direct",
)
PIPELINE_MODES: Final[tuple[str, ...]] = (
    "text_only",
    "tables+text",
    "force_ocr",
)
DIAGNOSTIC_KINDS: Final[tuple[str, ...]] = (
    "camelot_warning",
    "camelot_timeout",
    "ocr_fallback_warning",
    "unexpected_error",
)
_CAPTURED_WARNING_LOGGERS: Final[tuple[str, ...]] = (
    "src.analysis.extractor.legacy_helpers",
)
CANONICAL_TRUST_ORDER: Final[tuple[tuple[str, str, str], ...]] = (
    ("table", "exact", "direct"),
    ("table", "code_match", "direct"),
    ("table", "section_match", "direct"),
    ("text", "code_match", "direct"),
    ("ocr", "exact", "direct"),
    ("ocr", "code_match", "direct"),
    ("ocr", "section_match", "direct"),
    ("table", "keyword_match", "direct"),
    ("text", "keyword_match", "direct"),
    ("derived", "not_applicable", "derived"),
    ("table", "exact", "approximation"),
)
_SUITE_TIER_RANK: Final[dict[str, int]] = {
    suite_tier: index for index, suite_tier in enumerate(SUITE_TIERS)
}


@dataclass(frozen=True, slots=True)
class CandidateDescriptor:
    value: float
    match_type: str
    is_exact: bool
    candidate_quality: int = 50
    source: str | None = None
    match_semantics: str | None = None
    inference_mode: str | None = None
    reason_code: str | None = None
    signal_flags: tuple[str, ...] = ()
    conflict_count: int = 0
    postprocess_state: str = "none"
    authoritative_override: bool = False


@dataclass(frozen=True, slots=True)
class MetricExpectation:
    survives: bool
    value: float | None = None
    tolerance: float = 0.0
    expected_source: str | None = None
    source_strictness: str = "unspecified"


@dataclass(frozen=True, slots=True)
class CandidateThresholdCase:
    case_id: str
    suite_id: str
    suite_tier: str
    decision_surface: str
    risk_tags: tuple[str, ...]
    anchor: bool
    fixture_ref: str | None
    pipeline_mode: str | None
    metric_key: str
    candidate: CandidateDescriptor
    expected: MetricExpectation

    @property
    def outcome_ids(self) -> tuple[str, ...]:
        return (self.case_id,)


@dataclass(frozen=True, slots=True)
class ParseCase:
    case_id: str
    suite_id: str
    suite_tier: str
    decision_surface: str
    risk_tags: tuple[str, ...]
    anchor: bool
    fixture_ref: str | None
    pipeline_mode: str
    tables: tuple[dict[str, Any], ...]
    text: str
    expectations: dict[str, MetricExpectation]

    @property
    def outcome_ids(self) -> tuple[str, ...]:
        return tuple(
            f"{self.case_id}::{metric_key}" for metric_key in self.expectations
        )


@dataclass(frozen=True, slots=True)
class MergeCase:
    case_id: str
    suite_id: str
    suite_tier: str
    decision_surface: str
    risk_tags: tuple[str, ...]
    anchor: bool
    fixture_ref: str | None
    pipeline_mode: str | None
    metric_key: str
    llm_metadata: ExtractionMetadata
    expected_winner: str
    expected_source: str | None = None
    expected_authoritative_override: bool | None = None
    expected_reason_code: str | None = None
    fallback_candidate: CandidateDescriptor | None = None
    fallback_metadata: ExtractionMetadata | None = None

    @property
    def outcome_ids(self) -> tuple[str, ...]:
        return (self.case_id,)


CalibrationCase = CandidateThresholdCase | ParseCase | MergeCase


@dataclass(frozen=True, slots=True)
class CalibrationSuite:
    suite_id: str
    suite_tier: str
    cases: tuple[CalibrationCase, ...]

    @property
    def case_ids(self) -> tuple[str, ...]:
        return tuple(case.case_id for case in self.cases)

    @property
    def parse_cases(self) -> tuple[ParseCase, ...]:
        return tuple(case for case in self.cases if isinstance(case, ParseCase))

    @property
    def merge_cases(self) -> tuple[MergeCase, ...]:
        return tuple(case for case in self.cases if isinstance(case, MergeCase))


@dataclass(frozen=True, slots=True)
class CalibrationManifest:
    version: int
    threshold: float
    suites: tuple[CalibrationSuite, ...]

    @property
    def suite_ids(self) -> tuple[str, ...]:
        return tuple(suite.suite_id for suite in self.suites)

    @property
    def cases(self) -> tuple[CalibrationCase, ...]:
        return tuple(case for suite in self.suites for case in suite.cases)

    @property
    def parse_cases(self) -> tuple[ParseCase, ...]:
        return tuple(case for case in self.cases if isinstance(case, ParseCase))

    @property
    def merge_cases(self) -> tuple[MergeCase, ...]:
        return tuple(case for case in self.cases if isinstance(case, MergeCase))

    @property
    def threshold_cases(self) -> tuple[CandidateThresholdCase | ParseCase, ...]:
        return tuple(
            case
            for case in self.cases
            if isinstance(case, (CandidateThresholdCase, ParseCase))
        )

    @property
    def all_case_ids(self) -> tuple[str, ...]:
        return tuple(case.case_id for case in self.cases)

    @property
    def all_outcome_ids(self) -> tuple[str, ...]:
        outcome_ids: list[str] = []
        for case in self.cases:
            outcome_ids.extend(case.outcome_ids)
        return tuple(outcome_ids)


@dataclass(frozen=True, slots=True)
class ResolvedFixture:
    fixture_id: str
    path: Path
    sha256: str


@dataclass(frozen=True, slots=True)
class CapturedDiagnosticEvent:
    sequence: int
    kind: str
    message: str
    source: str
    logger_name: str | None = None
    warning_category: str | None = None


@dataclass(frozen=True, slots=True)
class FixtureParseBundle:
    tables: tuple[dict[str, Any], ...]
    text: str
    diagnostics: tuple[CapturedDiagnosticEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class EvaluationRuntime:
    name: str
    confidence_policy: ConfidencePolicy
    threshold: float
    strong_direct_threshold: float | None = None


@dataclass(frozen=True, slots=True)
class DiagnosticEvent:
    sequence: int
    kind: str
    suite_id: str
    suite_tier: str
    case_id: str
    fixture_ref: str | None
    message: str
    source: str
    logger_name: str | None = None
    warning_category: str | None = None


@dataclass(frozen=True, slots=True)
class CaseOutcome:
    outcome_id: str
    case_id: str
    suite_id: str
    suite_tier: str
    metric_key: str | None
    decision_surface: str
    risk_tags: tuple[str, ...]
    anchor: bool
    fixture_ref: str | None
    decision_type: str
    correct: bool
    outcome: str
    expected_outcome: str
    confidence: float
    source: str | None
    source_strictness: str = "unspecified"
    expected_source: str | None = None
    source_mismatch: bool = False
    authoritative_override: bool | None = None
    expected_authoritative_override: bool | None = None
    authoritative_override_mismatch: bool = False
    reason_code: str | None = None
    expected_reason_code: str | None = None
    reason_code_mismatch: bool = False
    survived: bool | None = None
    false_accept: bool = False
    false_reject: bool = False


@dataclass(frozen=True, slots=True)
class ReliabilityBin:
    lower: float
    upper: float
    count: int
    mean_confidence: float
    accuracy: float


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    total_cases: int
    correct_cases: int
    operational_accuracy: float
    false_accept_count: int
    false_reject_count: int
    survivor_count: int
    acceptance_rate: float
    boundary_density: float
    mean_confidence: float
    brier_score: float
    ece: float
    decision_surface_counts: dict[str, int]
    reliability_bins: tuple[ReliabilityBin, ...]


@dataclass(frozen=True, slots=True)
class SourceMismatchAudit:
    advisory_mismatches: tuple[str, ...]
    critical_mismatches: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PolicyEvaluationReport:
    runtime: EvaluationRuntime
    aggregate_summary: EvaluationSummary
    suite_summaries: dict[str, EvaluationSummary]
    case_outcomes: dict[str, CaseOutcome]
    source_mismatch_audit: SourceMismatchAudit
    diagnostics: tuple[DiagnosticEvent, ...] = ()

    @property
    def summary(self) -> EvaluationSummary:
        return self.aggregate_summary


@dataclass(frozen=True, slots=True)
class CaseDiff:
    outcome_id: str
    decision_type: str
    suite_id: str
    baseline: CaseOutcome
    candidate: CaseOutcome


@dataclass(frozen=True, slots=True)
class ThresholdSweepPoint:
    threshold: float
    operational_accuracy: float
    false_accept_count: int
    false_reject_count: int
    survivor_count: int
    acceptance_rate: float


@dataclass(frozen=True, slots=True)
class InvariantCheck:
    name: str
    passed: bool
    details: str


@dataclass(frozen=True, slots=True)
class PolicySettingDiff:
    setting: str
    baseline: float
    candidate: float


@dataclass(frozen=True, slots=True)
class ShadowConsumerPolicy:
    name: str
    threshold: float
    strong_direct_threshold: float


@dataclass(frozen=True, slots=True)
class CoverageAudit:
    required_surfaces: tuple[str, ...]
    expansion_priority_surfaces: tuple[str, ...]
    present_surfaces: dict[str, tuple[str, ...]]
    missing_required_surfaces: dict[str, tuple[str, ...]]
    anchor_surfaces: dict[str, tuple[str, ...]]
    real_fixture_anchor_surfaces: dict[str, tuple[str, ...]]
    underanchored_required_surfaces: dict[str, tuple[str, ...]]
    risk_tag_counts: dict[str, dict[str, int]]


@dataclass(frozen=True, slots=True)
class PolicyComparisonReport:
    manifest: CalibrationManifest
    baseline: PolicyEvaluationReport
    candidate: PolicyEvaluationReport
    shadow_policies: dict[str, PolicyEvaluationReport]
    case_diffs: dict[str, CaseDiff]
    threshold_sweep: dict[str, tuple[ThresholdSweepPoint, ...]]
    invariant_checks: tuple[InvariantCheck, ...]
    policy_diffs: tuple[PolicySettingDiff, ...]
    suite_case_diffs: dict[str, dict[str, CaseDiff]]
    coverage_audit: CoverageAudit | None = None


DEFAULT_SHADOW_POLICIES: Final[tuple[ShadowConsumerPolicy, ...]] = (
    ShadowConsumerPolicy(
        name="shadow_relaxed_consumer",
        threshold=0.5,
        strong_direct_threshold=0.65,
    ),
)


def _suite_sort_key(suite_id: str, suite_tier: str) -> tuple[int, str]:
    return (_SUITE_TIER_RANK.get(suite_tier, len(_SUITE_TIER_RANK)), suite_id)


class CalibrationCaseEvaluationError(RuntimeError):
    def __init__(
        self,
        original_exc: Exception,
        diagnostics: tuple[DiagnosticEvent, ...],
    ) -> None:
        super().__init__(str(original_exc))
        self.original_exc = original_exc
        self.diagnostics = diagnostics


class _DiagnosticLogHandler(logging.Handler):
    def __init__(self, recorder: Callable[..., None]) -> None:
        super().__init__(level=logging.WARNING)
        self._recorder = recorder

    def emit(self, record: logging.LogRecord) -> None:
        self._recorder(
            kind=_classify_diagnostic_kind(record.getMessage(), source="log"),
            message=record.getMessage(),
            source="log",
            logger_name=record.name,
        )


def _classify_diagnostic_kind(message: str, *, source: str) -> str:
    lowered = message.lower()
    if source == "exception":
        return "unexpected_error"
    if "camelot" in lowered and "timed out" in lowered:
        return "camelot_timeout"
    if "camelot" in lowered or "no tables found" in lowered or "image-based" in lowered:
        return "camelot_warning"
    if "ocr" in lowered:
        return "ocr_fallback_warning"
    return "camelot_warning" if source == "warning" else "ocr_fallback_warning"


@contextmanager
def _capture_fixture_diagnostics() -> Any:
    diagnostics: list[CapturedDiagnosticEvent] = []
    sequence = 0

    def _record(
        *,
        kind: str,
        message: str,
        source: str,
        logger_name: str | None = None,
        warning_category: str | None = None,
    ) -> None:
        nonlocal sequence
        sequence += 1
        diagnostics.append(
            CapturedDiagnosticEvent(
                sequence=sequence,
                kind=kind,
                message=message,
                source=source,
                logger_name=logger_name,
                warning_category=warning_category,
            )
        )

    handler = _DiagnosticLogHandler(_record)
    logger_state: list[
        tuple[logging.Logger, list[logging.Handler], int, bool, bool]
    ] = []

    with warnings.catch_warnings():
        warnings.simplefilter("always")
        original_showwarning = warnings.showwarning

        def _showwarning(
            message: warnings.WarningMessage | Warning,
            category: type[Warning],
            filename: str,
            lineno: int,
            file: Any | None = None,
            line: str | None = None,
        ) -> None:
            _record(
                kind=_classify_diagnostic_kind(str(message), source="warning"),
                message=str(message),
                source="warning",
                warning_category=category.__name__,
            )

        warnings.showwarning = _showwarning
        try:
            for logger_name in _CAPTURED_WARNING_LOGGERS:
                logger = logging.getLogger(logger_name)
                logger_state.append(
                    (
                        logger,
                        list(logger.handlers),
                        logger.level,
                        logger.propagate,
                        logger.disabled,
                    )
                )
                logger.handlers = [handler]
                logger.setLevel(logging.WARNING)
                logger.propagate = False
                logger.disabled = False
            yield diagnostics
        except Exception as exc:
            _record(
                kind=_classify_diagnostic_kind(str(exc), source="exception"),
                message=f"{type(exc).__name__}: {exc}",
                source="exception",
            )
            raise
        finally:
            warnings.showwarning = original_showwarning
            for logger, handlers, level, propagate, disabled in reversed(logger_state):
                logger.handlers = handlers
                logger.setLevel(level)
                logger.propagate = propagate
                logger.disabled = disabled


def _load_json(path: Path) -> dict[str, Any] | list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _build_candidate_descriptor(payload: dict[str, Any]) -> CandidateDescriptor:
    return CandidateDescriptor(
        value=float(payload["value"]),
        match_type=payload["match_type"],
        is_exact=bool(payload["is_exact"]),
        candidate_quality=int(payload.get("candidate_quality", 50)),
        source=payload.get("source"),
        match_semantics=payload.get("match_semantics"),
        inference_mode=payload.get("inference_mode"),
        reason_code=payload.get("reason_code"),
        signal_flags=tuple(payload.get("signal_flags", [])),
        conflict_count=int(payload.get("conflict_count", 0)),
        postprocess_state=payload.get("postprocess_state", "none"),
        authoritative_override=bool(payload.get("authoritative_override", False)),
    )


def _build_metadata(payload: dict[str, Any]) -> ExtractionMetadata:
    return ExtractionMetadata(
        value=payload.get("value"),
        confidence=float(payload["confidence"]),
        source=payload["source"],
        evidence_version=payload.get("evidence_version", "v2"),
        match_semantics=payload.get("match_semantics", "not_applicable"),
        inference_mode=payload.get("inference_mode", "direct"),
        postprocess_state=payload.get("postprocess_state", "none"),
        reason_code=payload.get("reason_code"),
        signal_flags=list(payload.get("signal_flags", [])),
        candidate_quality=payload.get("candidate_quality"),
        authoritative_override=bool(payload.get("authoritative_override", False)),
    )


def _build_expectation(payload: dict[str, Any]) -> MetricExpectation:
    expected_source = payload.get("expected_source")
    source_strictness = payload.get("source_strictness", "unspecified")
    if source_strictness not in SOURCE_STRICTNESS_VALUES:
        raise ValueError(f"Unsupported source strictness: {source_strictness!r}")
    if source_strictness == "unspecified" and expected_source is not None:
        raise ValueError(
            "expected_source requires source_strictness 'advisory' or 'critical'"
        )
    if source_strictness != "unspecified" and not expected_source:
        raise ValueError(
            "source strictness 'advisory' or 'critical' requires expected_source"
        )
    return MetricExpectation(
        survives=bool(payload["survives"]),
        value=payload.get("value"),
        tolerance=float(payload.get("tolerance", 0.0)),
        expected_source=expected_source,
        source_strictness=source_strictness,
    )


def _build_merge_expectation(
    payload: dict[str, Any],
) -> tuple[str, str | None, bool | None, str | None]:
    expected_winner = payload["winner"]
    expected_source = payload.get("expected_source")
    expected_authoritative_override = payload.get("expected_authoritative_override")
    if expected_authoritative_override is not None:
        expected_authoritative_override = bool(expected_authoritative_override)
    expected_reason_code = payload.get("expected_reason_code")
    if expected_reason_code is not None and not expected_reason_code:
        raise ValueError("expected_reason_code cannot be empty")
    return (
        expected_winner,
        expected_source,
        expected_authoritative_override,
        expected_reason_code,
    )


def _validate_case_contract(
    raw_case: dict[str, Any],
    *,
    suite_id: str,
    suite_tier: str,
) -> tuple[str, tuple[str, ...], bool, str | None, str | None]:
    decision_surface = raw_case["decision_surface"]
    if decision_surface not in DECISION_SURFACES:
        raise ValueError(f"Unsupported decision surface: {decision_surface!r}")

    risk_tags = tuple(raw_case.get("risk_tags", []))
    unknown_tags = sorted(set(risk_tags) - set(RISK_TAG_VOCABULARY))
    if unknown_tags:
        raise ValueError(f"Unknown risk tag(s): {', '.join(unknown_tags)}")

    anchor = bool(raw_case.get("anchor", False))
    fixture_ref = raw_case.get("fixture_ref")
    pipeline_mode = raw_case.get("pipeline_mode")
    if pipeline_mode is not None and pipeline_mode not in PIPELINE_MODES:
        raise ValueError(f"Unsupported pipeline_mode: {pipeline_mode!r}")

    if raw_case.get("suite_id") not in (None, suite_id):
        raise ValueError(
            f"Case {raw_case['case_id']} has mismatched suite_id "
            f"{raw_case['suite_id']!r} != {suite_id!r}"
        )
    if raw_case.get("suite_tier") not in (None, suite_tier):
        raise ValueError(
            f"Case {raw_case['case_id']} has mismatched suite_tier "
            f"{raw_case['suite_tier']!r} != {suite_tier!r}"
        )

    return decision_surface, risk_tags, anchor, fixture_ref, pipeline_mode


def _load_suite_file(path: Path) -> tuple[int, float, CalibrationSuite]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"Calibration suite manifest must be a JSON object: {path}")

    version = int(payload["version"])
    suite_id = payload["suite_id"]
    suite_tier = payload["suite_tier"]
    if suite_tier not in SUITE_TIERS:
        raise ValueError(f"Unsupported suite tier: {suite_tier!r}")

    cases: list[CalibrationCase] = []
    for raw_case in payload.get("cases", []):
        case_id = raw_case["case_id"]
        decision_surface, risk_tags, anchor, fixture_ref, pipeline_mode = (
            _validate_case_contract(raw_case, suite_id=suite_id, suite_tier=suite_tier)
        )
        kind = raw_case["kind"]

        if kind == "candidate_threshold":
            cases.append(
                CandidateThresholdCase(
                    case_id=case_id,
                    suite_id=suite_id,
                    suite_tier=suite_tier,
                    decision_surface=decision_surface,
                    risk_tags=risk_tags,
                    anchor=anchor,
                    fixture_ref=fixture_ref,
                    pipeline_mode=pipeline_mode,
                    metric_key=raw_case["metric_key"],
                    candidate=_build_candidate_descriptor(raw_case["candidate"]),
                    expected=_build_expectation(raw_case["expected"]),
                )
            )
            continue

        if kind == "parse":
            expectations = {
                metric_key: _build_expectation(expectation_payload)
                for metric_key, expectation_payload in sorted(
                    raw_case["expectations"].items()
                )
            }
            if not expectations:
                raise ValueError(
                    f"Parse case {case_id} requires at least one expectation"
                )
            cases.append(
                ParseCase(
                    case_id=case_id,
                    suite_id=suite_id,
                    suite_tier=suite_tier,
                    decision_surface=decision_surface,
                    risk_tags=risk_tags,
                    anchor=anchor,
                    fixture_ref=fixture_ref,
                    pipeline_mode=pipeline_mode or "tables+text",
                    tables=tuple(copy.deepcopy(raw_case.get("tables", []))),
                    text=raw_case.get("text", ""),
                    expectations=expectations,
                )
            )
            continue

        if kind == "merge":
            fallback_candidate = raw_case.get("fallback_candidate")
            fallback_metadata = raw_case.get("fallback_metadata")
            if fallback_candidate is None and fallback_metadata is None:
                raise ValueError(
                    "Merge cases require fallback_candidate or fallback_metadata"
                )
            (
                expected_winner,
                expected_source,
                expected_authoritative_override,
                expected_reason_code,
            ) = _build_merge_expectation(raw_case["expected"])
            cases.append(
                MergeCase(
                    case_id=case_id,
                    suite_id=suite_id,
                    suite_tier=suite_tier,
                    decision_surface=decision_surface,
                    risk_tags=risk_tags,
                    anchor=anchor,
                    fixture_ref=fixture_ref,
                    pipeline_mode=pipeline_mode,
                    metric_key=raw_case["metric_key"],
                    llm_metadata=_build_metadata(raw_case["llm_metadata"]),
                    expected_winner=expected_winner,
                    expected_source=expected_source,
                    expected_authoritative_override=expected_authoritative_override,
                    expected_reason_code=expected_reason_code,
                    fallback_candidate=(
                        _build_candidate_descriptor(fallback_candidate)
                        if fallback_candidate is not None
                        else None
                    ),
                    fallback_metadata=(
                        _build_metadata(fallback_metadata)
                        if fallback_metadata is not None
                        else None
                    ),
                )
            )
            continue

        raise ValueError(f"Unsupported calibration case kind: {kind!r}")

    cases.sort(key=lambda case: case.case_id)
    return (
        version,
        float(payload.get("threshold", 0.5)),
        CalibrationSuite(
            suite_id=suite_id,
            suite_tier=suite_tier,
            cases=tuple(cases),
        ),
    )


def load_calibration_manifest(
    path: Path | str = DEFAULT_MANIFEST_PATH,
    *,
    suite: str = "all",
) -> CalibrationManifest:
    manifest_path = Path(path)
    if suite not in {"all", *SUITE_TIERS}:
        raise ValueError(f"Unsupported suite selector: {suite!r}")

    if manifest_path.is_dir():
        suite_files = sorted(
            file_path
            for file_path in manifest_path.glob("*.json")
            if file_path.is_file()
        )
    else:
        suite_files = [manifest_path]

    if not suite_files:
        raise ValueError(f"No calibration suite manifests found at {manifest_path}")

    version: int | None = None
    threshold: float | None = None
    suites: list[CalibrationSuite] = []
    seen_case_ids: set[str] = set()

    for suite_file in suite_files:
        suite_version, suite_threshold, calibration_suite = _load_suite_file(suite_file)
        if suite not in {
            "all",
            calibration_suite.suite_id,
            calibration_suite.suite_tier,
        }:
            continue
        if version is None:
            version = suite_version
        elif version != suite_version:
            raise ValueError(
                "Calibration suite manifests must share the same schema version"
            )
        if threshold is None:
            threshold = suite_threshold
        elif threshold != suite_threshold:
            raise ValueError(
                "Calibration suite manifests must share the same threshold"
            )

        for case_id in calibration_suite.case_ids:
            if case_id in seen_case_ids:
                raise ValueError(f"Duplicate calibration case id: {case_id}")
            seen_case_ids.add(case_id)
        suites.append(calibration_suite)

    if not suites:
        raise ValueError(
            f"No calibration suites matched selector {suite!r} at {manifest_path}"
        )

    suites.sort(
        key=lambda suite_item: _suite_sort_key(
            suite_item.suite_id, suite_item.suite_tier
        )
    )
    return CalibrationManifest(
        version=version or 2,
        threshold=threshold if threshold is not None else 0.5,
        suites=tuple(suites),
    )


@lru_cache(maxsize=16)
def _load_fixture_catalog(
    fixture_manifest_path: str,
) -> dict[str, ResolvedFixture]:
    manifest_path = Path(fixture_manifest_path)
    payload = _load_json(manifest_path)
    if not isinstance(payload, list):
        raise ValueError("Fixture manifest must be a JSON array")

    fixtures: dict[str, ResolvedFixture] = {}
    for item in payload:
        fixture_id = item["id"]
        fixture_path = _resolve_manifest_fixture_path(
            manifest_path,
            item["filename"],
        )
        fixtures[fixture_id] = ResolvedFixture(
            fixture_id=fixture_id,
            path=fixture_path,
            sha256=item["sha256"],
        )
    return fixtures


def _resolve_manifest_fixture_path(manifest_path: Path, filename: str) -> Path:
    normalized_filename = filename.replace("\\", "/")
    if normalized_filename.startswith("/") or (
        len(normalized_filename) > 1 and normalized_filename[1] == ":"
    ):
        raise ValueError(
            f"Fixture filename must be relative to the committed fixture manifest root: {filename!r}"
        )
    candidate = (manifest_path.parent / Path(normalized_filename)).resolve()
    try:
        candidate.relative_to(manifest_path.parent.resolve())
    except ValueError as exc:
        raise ValueError(
            f"Fixture filename must resolve inside the committed fixture manifest root: {filename!r}"
        ) from exc
    return candidate


def resolve_fixture_ref(
    fixture_id: str,
    *,
    fixture_manifest_path: Path | str = DEFAULT_FIXTURE_MANIFEST_PATH,
) -> ResolvedFixture:
    catalog = _load_fixture_catalog(str(Path(fixture_manifest_path).resolve()))
    try:
        return catalog[fixture_id]
    except KeyError as exc:
        raise ValueError(f"Unknown fixture_ref: {fixture_id}") from exc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=16)
def _load_fixture_parse_bundle(
    fixture_manifest_path: str,
    fixture_id: str,
    pipeline_mode: str,
) -> FixtureParseBundle:
    if pipeline_mode not in PIPELINE_MODES:
        raise ValueError(f"Unsupported pipeline_mode: {pipeline_mode!r}")

    resolved = resolve_fixture_ref(
        fixture_id,
        fixture_manifest_path=Path(fixture_manifest_path),
    )
    actual_sha256 = _sha256(resolved.path)
    if actual_sha256 != resolved.sha256:
        raise ValueError(
            f"Fixture integrity mismatch for {fixture_id}: "
            f"{actual_sha256} != {resolved.sha256}"
        )

    from src.analysis import pdf_extractor

    with _capture_fixture_diagnostics() as captured_diagnostics:
        if pipeline_mode == "force_ocr":
            # `force_ocr` is an OCR-only calibration execution mode, not a
            # document classification. It intentionally bypasses table extraction.
            text = pdf_extractor.extract_text_from_scanned(str(resolved.path))
            tables: list[dict[str, Any]] = []
        else:
            text = pdf_extractor.extract_text(str(resolved.path))
            if pipeline_mode == "text_only":
                tables = []
            else:
                tables = pdf_extractor.extract_tables(str(resolved.path))
    return FixtureParseBundle(
        tables=tuple(copy.deepcopy(tables)),
        text=text,
        diagnostics=tuple(captured_diagnostics),
    )


def _load_fixture_parse_inputs(
    fixture_manifest_path: str,
    fixture_id: str,
    pipeline_mode: str,
) -> tuple[list[dict[str, Any]], str]:
    bundle = _load_fixture_parse_bundle(
        fixture_manifest_path,
        fixture_id,
        pipeline_mode,
    )
    return copy.deepcopy(list(bundle.tables)), bundle.text


_load_fixture_parse_inputs.cache_clear = _load_fixture_parse_bundle.cache_clear  # type: ignore[attr-defined]


def _prepare_parse_inputs(
    case: ParseCase,
    *,
    fixture_manifest_path: Path | str,
) -> tuple[list[dict[str, Any]], str, tuple[CapturedDiagnosticEvent, ...]]:
    if case.fixture_ref is None:
        return copy.deepcopy(list(case.tables)), case.text, ()
    bundle = _load_fixture_parse_bundle(
        str(Path(fixture_manifest_path).resolve()),
        case.fixture_ref,
        case.pipeline_mode,
    )
    return copy.deepcopy(list(bundle.tables)), bundle.text, bundle.diagnostics


def _to_candidate(descriptor: CandidateDescriptor) -> RawMetricCandidate:
    return RawMetricCandidate(
        value=descriptor.value,
        match_type=descriptor.match_type,
        is_exact=descriptor.is_exact,
        candidate_quality=descriptor.candidate_quality,
        source=descriptor.source,
        match_semantics=descriptor.match_semantics,
        inference_mode=descriptor.inference_mode,
        reason_code=descriptor.reason_code,
        signal_flags=list(descriptor.signal_flags),
        conflict_count=descriptor.conflict_count,
        postprocess_state=descriptor.postprocess_state,
        authoritative_override=descriptor.authoritative_override,
    )


def _evaluate_threshold_expectation(
    *,
    outcome_id: str,
    case_id: str,
    suite_id: str,
    suite_tier: str,
    decision_surface: str,
    risk_tags: tuple[str, ...],
    anchor: bool,
    fixture_ref: str | None,
    decision_type: str,
    metric_key: str,
    metadata: ExtractionMetadata,
    expectation: MetricExpectation,
    threshold: float,
) -> CaseOutcome:
    filtered, _ = apply_confidence_filter({metric_key: metadata}, threshold=threshold)
    survives = filtered[metric_key] is not None
    actual_source = metadata.source if metadata.value is not None else None
    source_mismatch = (
        survives
        and expectation.expected_source is not None
        and actual_source != expectation.expected_source
    )
    correct = survives == expectation.survives
    if correct and expectation.value is not None and survives:
        correct = (
            abs((metadata.value or 0.0) - expectation.value) <= expectation.tolerance
        )
    if correct and expectation.source_strictness == "critical" and source_mismatch:
        correct = False

    expected_outcome = (
        f"survive:{expectation.expected_source}"
        if expectation.survives and expectation.expected_source is not None
        else ("survive" if expectation.survives else "absent")
    )
    outcome = (
        f"survive:{actual_source}"
        if survives and actual_source is not None
        else "absent"
    )
    return CaseOutcome(
        outcome_id=outcome_id,
        case_id=case_id,
        suite_id=suite_id,
        suite_tier=suite_tier,
        metric_key=metric_key,
        decision_surface=decision_surface,
        risk_tags=risk_tags,
        anchor=anchor,
        fixture_ref=fixture_ref,
        decision_type=decision_type,
        correct=correct,
        outcome=outcome,
        expected_outcome=expected_outcome,
        confidence=metadata.confidence,
        source=actual_source,
        source_strictness=expectation.source_strictness,
        expected_source=expectation.expected_source,
        source_mismatch=source_mismatch,
        survived=survives,
        false_accept=(not expectation.survives and survives),
        false_reject=(expectation.survives and not survives),
    )


def _evaluate_candidate_threshold_case(
    case: CandidateThresholdCase,
    runtime: EvaluationRuntime,
) -> CaseOutcome:
    metadata = build_metadata_from_candidate(
        _to_candidate(case.candidate),
        confidence_policy=runtime.confidence_policy,
    )
    return _evaluate_threshold_expectation(
        outcome_id=case.case_id,
        case_id=case.case_id,
        suite_id=case.suite_id,
        suite_tier=case.suite_tier,
        decision_surface=case.decision_surface,
        risk_tags=case.risk_tags,
        anchor=case.anchor,
        fixture_ref=case.fixture_ref,
        decision_type="threshold",
        metric_key=case.metric_key,
        metadata=metadata,
        expectation=case.expected,
        threshold=runtime.threshold,
    )


def _materialize_case_diagnostics(
    case: ParseCase,
    captured: tuple[CapturedDiagnosticEvent, ...],
) -> list[DiagnosticEvent]:
    return [
        DiagnosticEvent(
            sequence=event.sequence,
            kind=event.kind,
            suite_id=case.suite_id,
            suite_tier=case.suite_tier,
            case_id=case.case_id,
            fixture_ref=case.fixture_ref,
            message=event.message,
            source=event.source,
            logger_name=event.logger_name,
            warning_category=event.warning_category,
        )
        for event in captured
    ]


def _evaluate_parse_case(
    case: ParseCase,
    runtime: EvaluationRuntime,
    *,
    fixture_manifest_path: Path | str,
) -> tuple[list[CaseOutcome], list[DiagnosticEvent]]:
    tables, text, captured_diagnostics = _prepare_parse_inputs(
        case,
        fixture_manifest_path=fixture_manifest_path,
    )
    diagnostics = _materialize_case_diagnostics(case, captured_diagnostics)
    try:
        trace = build_extractor_trace(tables, text)
        metadata, _ = build_metadata_from_trace(
            trace,
            confidence_policy=runtime.confidence_policy,
            include_decision_logs=True,
        )
    except Exception as exc:
        diagnostics.append(
            DiagnosticEvent(
                sequence=len(diagnostics) + 1,
                kind="unexpected_error",
                suite_id=case.suite_id,
                suite_tier=case.suite_tier,
                case_id=case.case_id,
                fixture_ref=case.fixture_ref,
                message=f"{type(exc).__name__}: {exc}",
                source="exception",
            )
        )
        raise CalibrationCaseEvaluationError(exc, tuple(diagnostics)) from exc

    outcomes = [
        _evaluate_threshold_expectation(
            outcome_id=f"{case.case_id}::{metric_key}",
            case_id=case.case_id,
            suite_id=case.suite_id,
            suite_tier=case.suite_tier,
            decision_surface=case.decision_surface,
            risk_tags=case.risk_tags,
            anchor=case.anchor,
            fixture_ref=case.fixture_ref,
            decision_type="winner",
            metric_key=metric_key,
            metadata=metadata[metric_key],
            expectation=expectation,
            threshold=runtime.threshold,
        )
        for metric_key, expectation in sorted(case.expectations.items())
    ]
    return outcomes, diagnostics


def _evaluate_merge_case(
    case: MergeCase,
    runtime: EvaluationRuntime,
) -> CaseOutcome:
    if case.fallback_candidate is not None:
        fallback_metadata = build_metadata_from_candidate(
            _to_candidate(case.fallback_candidate),
            confidence_policy=runtime.confidence_policy,
        )
    else:
        fallback_metadata = case.fallback_metadata

    prefer_llm = should_prefer_llm_metric(
        case.llm_metadata,
        fallback_metadata,
        threshold=runtime.threshold,
        strong_direct_threshold=(
            runtime.strong_direct_threshold
            if runtime.strong_direct_threshold is not None
            else runtime.confidence_policy.strong_direct_threshold
        ),
    )
    actual_winner = "llm" if prefer_llm else "fallback"
    selected = case.llm_metadata if prefer_llm else fallback_metadata
    confidence = selected.confidence if selected is not None else 0.0
    source = selected.source if selected is not None else None
    authoritative_override = (
        selected.authoritative_override if selected is not None else None
    )
    reason_code = selected.reason_code if selected is not None else None
    source_mismatch = (
        case.expected_source is not None and source != case.expected_source
    )
    authoritative_override_mismatch = (
        case.expected_authoritative_override is not None
        and authoritative_override != case.expected_authoritative_override
    )
    reason_code_mismatch = (
        case.expected_reason_code is not None
        and reason_code != case.expected_reason_code
    )
    correct = actual_winner == case.expected_winner
    if correct and source_mismatch:
        correct = False
    if correct and authoritative_override_mismatch:
        correct = False
    if correct and reason_code_mismatch:
        correct = False

    expected_outcome_parts = [case.expected_winner]
    if case.expected_source is not None:
        expected_outcome_parts.append(case.expected_source)
    if case.expected_authoritative_override is not None:
        expected_outcome_parts.append(
            f"authoritative_override={case.expected_authoritative_override!s}"
        )
    if case.expected_reason_code is not None:
        expected_outcome_parts.append(f"reason_code={case.expected_reason_code}")

    actual_outcome_parts = [actual_winner]
    if source is not None:
        actual_outcome_parts.append(source)
    if authoritative_override is not None:
        actual_outcome_parts.append(
            f"authoritative_override={authoritative_override!s}"
        )
    if reason_code is not None:
        actual_outcome_parts.append(f"reason_code={reason_code}")

    return CaseOutcome(
        outcome_id=case.case_id,
        case_id=case.case_id,
        suite_id=case.suite_id,
        suite_tier=case.suite_tier,
        metric_key=case.metric_key,
        decision_surface=case.decision_surface,
        risk_tags=case.risk_tags,
        anchor=case.anchor,
        fixture_ref=case.fixture_ref,
        decision_type="merge",
        correct=correct,
        outcome="|".join(actual_outcome_parts),
        expected_outcome="|".join(expected_outcome_parts),
        confidence=confidence,
        source=source,
        source_strictness=(
            "critical" if case.expected_source is not None else "unspecified"
        ),
        expected_source=case.expected_source,
        source_mismatch=source_mismatch,
        authoritative_override=authoritative_override,
        expected_authoritative_override=case.expected_authoritative_override,
        authoritative_override_mismatch=authoritative_override_mismatch,
        reason_code=reason_code,
        expected_reason_code=case.expected_reason_code,
        reason_code_mismatch=reason_code_mismatch,
        survived=None,
    )


def _build_reliability_bins(outcomes: list[CaseOutcome]) -> tuple[ReliabilityBin, ...]:
    bins: list[ReliabilityBin] = []
    for index in range(5):
        lower = index / 5
        upper = (index + 1) / 5
        bucket = [
            outcome
            for outcome in outcomes
            if lower <= outcome.confidence < upper
            or (index == 4 and outcome.confidence == 1.0)
        ]
        if not bucket:
            bins.append(
                ReliabilityBin(
                    lower=lower,
                    upper=upper,
                    count=0,
                    mean_confidence=0.0,
                    accuracy=0.0,
                )
            )
            continue
        bins.append(
            ReliabilityBin(
                lower=lower,
                upper=upper,
                count=len(bucket),
                mean_confidence=sum(item.confidence for item in bucket) / len(bucket),
                accuracy=sum(1 for item in bucket if item.correct) / len(bucket),
            )
        )
    return tuple(bins)


def _build_summary(
    outcomes: list[CaseOutcome],
    *,
    threshold: float,
) -> EvaluationSummary:
    total_cases = len(outcomes)
    correct_cases = sum(1 for outcome in outcomes if outcome.correct)
    false_accept_count = sum(1 for outcome in outcomes if outcome.false_accept)
    false_reject_count = sum(1 for outcome in outcomes if outcome.false_reject)
    threshold_outcomes = [
        outcome for outcome in outcomes if outcome.survived is not None
    ]
    survivor_count = sum(1 for outcome in threshold_outcomes if outcome.survived)
    acceptance_rate = (
        survivor_count / len(threshold_outcomes) if threshold_outcomes else 0.0
    )
    boundary_density = (
        sum(1 for outcome in outcomes if abs(outcome.confidence - threshold) <= 0.05)
        / total_cases
        if total_cases
        else 0.0
    )
    mean_confidence = (
        sum(outcome.confidence for outcome in outcomes) / total_cases
        if total_cases
        else 0.0
    )
    brier_score = (
        sum((outcome.confidence - float(outcome.correct)) ** 2 for outcome in outcomes)
        / total_cases
        if total_cases
        else 0.0
    )
    reliability_bins = _build_reliability_bins(outcomes)
    ece = 0.0
    if total_cases:
        for bucket in reliability_bins:
            if bucket.count == 0:
                continue
            ece += (bucket.count / total_cases) * abs(
                bucket.accuracy - bucket.mean_confidence
            )

    surface_counter = Counter(outcome.decision_surface for outcome in outcomes)
    decision_surface_counts = {
        surface: surface_counter.get(surface, 0) for surface in DECISION_SURFACES
    }

    return EvaluationSummary(
        total_cases=total_cases,
        correct_cases=correct_cases,
        operational_accuracy=(correct_cases / total_cases) if total_cases else 0.0,
        false_accept_count=false_accept_count,
        false_reject_count=false_reject_count,
        survivor_count=survivor_count,
        acceptance_rate=acceptance_rate,
        boundary_density=boundary_density,
        mean_confidence=mean_confidence,
        brier_score=brier_score,
        ece=ece,
        decision_surface_counts=decision_surface_counts,
        reliability_bins=reliability_bins,
    )


def _build_source_mismatch_audit(outcomes: list[CaseOutcome]) -> SourceMismatchAudit:
    advisory = sorted(
        outcome.outcome_id
        for outcome in outcomes
        if outcome.source_mismatch and outcome.source_strictness == "advisory"
    )
    critical = sorted(
        outcome.outcome_id
        for outcome in outcomes
        if outcome.source_mismatch and outcome.source_strictness == "critical"
    )
    return SourceMismatchAudit(
        advisory_mismatches=tuple(advisory),
        critical_mismatches=tuple(critical),
    )


def _build_threshold_sweep(
    manifest: CalibrationManifest,
    *,
    policy: ConfidencePolicy,
    strong_direct_threshold: float | None,
    fixture_manifest_path: Path | str,
) -> tuple[ThresholdSweepPoint, ...]:
    thresholds = sorted(
        {
            round(max(0.0, min(1.0, manifest.threshold + offset)), 2)
            for offset in SWEEP_OFFSETS
        }
    )
    sweep_points: list[ThresholdSweepPoint] = []
    for threshold in thresholds:
        runtime = EvaluationRuntime(
            name=f"{policy.name}@{threshold:.2f}",
            confidence_policy=policy,
            threshold=threshold,
            strong_direct_threshold=strong_direct_threshold,
        )
        summary = evaluate_runtime(
            manifest,
            runtime,
            fixture_manifest_path=fixture_manifest_path,
        ).summary
        sweep_points.append(
            ThresholdSweepPoint(
                threshold=threshold,
                operational_accuracy=summary.operational_accuracy,
                false_accept_count=summary.false_accept_count,
                false_reject_count=summary.false_reject_count,
                survivor_count=summary.survivor_count,
                acceptance_rate=summary.acceptance_rate,
            )
        )
    return tuple(sweep_points)


def _build_invariant_checks(
    baseline_policy: ConfidencePolicy,
    candidate_policy: ConfidencePolicy,
) -> tuple[InvariantCheck, ...]:
    checks: list[InvariantCheck] = []
    for left, right in zip(CANONICAL_TRUST_ORDER, CANONICAL_TRUST_ORDER[1:]):
        baseline_cmp = baseline_policy.compare_profile_trust(left, right)
        candidate_cmp = candidate_policy.compare_profile_trust(left, right)
        checks.append(
            InvariantCheck(
                name=f"trust_order:{left}>{right}",
                passed=(baseline_cmp > 0 and candidate_cmp > 0),
                details=(
                    f"baseline={baseline_cmp}, candidate={candidate_cmp}, "
                    f"left_rank={candidate_policy.get_profile(left).rank}, "
                    f"right_rank={candidate_policy.get_profile(right).rank}"
                ),
            )
        )

    baseline_override = baseline_policy.get_profile(
        ("issuer_fallback", "not_applicable", "policy_override")
    ).baseline_confidence
    candidate_override = candidate_policy.get_profile(
        ("issuer_fallback", "not_applicable", "policy_override")
    ).baseline_confidence
    checks.append(
        InvariantCheck(
            name="policy_override_confidence_unchanged",
            passed=(baseline_override == candidate_override == 0.95),
            details=f"baseline={baseline_override:.2f}, candidate={candidate_override:.2f}",
        )
    )
    checks.append(
        InvariantCheck(
            name="strong_direct_threshold_unchanged",
            passed=(
                baseline_policy.strong_direct_threshold
                == candidate_policy.strong_direct_threshold
            ),
            details=(
                f"baseline={baseline_policy.strong_direct_threshold:.2f}, "
                f"candidate={candidate_policy.strong_direct_threshold:.2f}"
            ),
        )
    )
    return tuple(checks)


def _build_policy_diffs(
    baseline_policy: ConfidencePolicy,
    candidate_policy: ConfidencePolicy,
) -> tuple[PolicySettingDiff, ...]:
    diffs: list[PolicySettingDiff] = []
    for profile_key in baseline_policy.profiles:
        baseline_profile = baseline_policy.get_profile(profile_key)
        candidate_profile = candidate_policy.get_profile(profile_key)
        if (
            baseline_profile.baseline_confidence
            != candidate_profile.baseline_confidence
        ):
            diffs.append(
                PolicySettingDiff(
                    setting=(
                        "profile:" f"{profile_key[0]}/{profile_key[1]}/{profile_key[2]}"
                    ),
                    baseline=baseline_profile.baseline_confidence,
                    candidate=candidate_profile.baseline_confidence,
                )
            )

    for baseline_band, candidate_band in zip(
        baseline_policy.quality_bands,
        candidate_policy.quality_bands,
    ):
        if baseline_band.delta != candidate_band.delta:
            band_name = (
                f"quality_band>={baseline_band.minimum_quality}"
                if baseline_band.minimum_quality is not None
                else "quality_band<fallback"
            )
            diffs.append(
                PolicySettingDiff(
                    setting=band_name,
                    baseline=baseline_band.delta,
                    candidate=candidate_band.delta,
                )
            )

    scalar_fields = (
        (
            "structural_bonus_delta",
            baseline_policy.structural_bonus_delta,
            candidate_policy.structural_bonus_delta,
        ),
        (
            "guardrail_penalty_delta",
            baseline_policy.guardrail_penalty_delta,
            candidate_policy.guardrail_penalty_delta,
        ),
        (
            "conflict_penalty_step",
            baseline_policy.conflict_penalty_step,
            candidate_policy.conflict_penalty_step,
        ),
        (
            "conflict_penalty_cap",
            baseline_policy.conflict_penalty_cap,
            candidate_policy.conflict_penalty_cap,
        ),
        (
            "strong_direct_threshold",
            baseline_policy.strong_direct_threshold,
            candidate_policy.strong_direct_threshold,
        ),
    )
    for name, baseline_value, candidate_value in scalar_fields:
        if baseline_value != candidate_value:
            diffs.append(
                PolicySettingDiff(
                    setting=name,
                    baseline=baseline_value,
                    candidate=candidate_value,
                )
            )
    return tuple(diffs)


def _build_coverage_audit(manifest: CalibrationManifest) -> CoverageAudit:
    suite_case_map = {suite_id: [] for suite_id in SUITE_TIERS}
    suite_case_map.update(
        {suite.suite_id: list(suite.cases) for suite in manifest.suites}
    )
    suite_case_map["all"] = list(manifest.cases)

    present_surfaces: dict[str, tuple[str, ...]] = {}
    missing_required_surfaces: dict[str, tuple[str, ...]] = {}
    anchor_surfaces: dict[str, tuple[str, ...]] = {}
    real_fixture_anchor_surfaces: dict[str, tuple[str, ...]] = {}
    underanchored_required_surfaces: dict[str, tuple[str, ...]] = {}
    risk_tag_counts: dict[str, dict[str, int]] = {}

    for scope, scoped_cases in suite_case_map.items():
        surfaces = sorted({case.decision_surface for case in scoped_cases})
        anchored = sorted(
            {case.decision_surface for case in scoped_cases if case.anchor}
        )
        real_fixture_anchored = sorted(
            {
                case.decision_surface
                for case in scoped_cases
                if case.anchor and case.fixture_ref is not None
            }
        )
        missing = sorted(set(REQUIRED_DECISION_SURFACES) - set(surfaces))
        if scope in {"gated", "all"}:
            underanchored = sorted(
                set(REQUIRED_DECISION_SURFACES) - set(real_fixture_anchored)
            )
        else:
            underanchored = []

        tag_counter = Counter(tag for case in scoped_cases for tag in case.risk_tags)
        present_surfaces[scope] = tuple(surfaces)
        missing_required_surfaces[scope] = tuple(missing)
        anchor_surfaces[scope] = tuple(anchored)
        real_fixture_anchor_surfaces[scope] = tuple(real_fixture_anchored)
        underanchored_required_surfaces[scope] = tuple(underanchored)
        risk_tag_counts[scope] = dict(sorted(tag_counter.items()))

    return CoverageAudit(
        required_surfaces=REQUIRED_DECISION_SURFACES,
        expansion_priority_surfaces=EXPANSION_PRIORITY_SURFACES,
        present_surfaces=present_surfaces,
        missing_required_surfaces=missing_required_surfaces,
        anchor_surfaces=anchor_surfaces,
        real_fixture_anchor_surfaces=real_fixture_anchor_surfaces,
        underanchored_required_surfaces=underanchored_required_surfaces,
        risk_tag_counts=risk_tag_counts,
    )


def _diagnostic_event_to_dict(event: DiagnosticEvent) -> dict[str, Any]:
    return {
        "sequence": event.sequence,
        "kind": event.kind,
        "suite_id": event.suite_id,
        "suite_tier": event.suite_tier,
        "case_id": event.case_id,
        "fixture_ref": event.fixture_ref,
        "message": event.message,
        "source": event.source,
        "logger_name": event.logger_name,
        "warning_category": event.warning_category,
    }


def _build_diagnostics_export(
    report_obj: PolicyEvaluationReport,
) -> dict[str, Any]:
    aggregate_counts = {kind: 0 for kind in DIAGNOSTIC_KINDS}
    suite_counts = {
        suite_id: {kind: 0 for kind in DIAGNOSTIC_KINDS}
        for suite_id in report_obj.suite_summaries
    }
    case_events: dict[str, list[dict[str, Any]]] = {}
    unexpected_diagnostics: list[dict[str, Any]] = []

    for event in report_obj.diagnostics:
        aggregate_counts[event.kind] += 1
        suite_counts.setdefault(
            event.suite_id,
            {kind: 0 for kind in DIAGNOSTIC_KINDS},
        )
        suite_counts[event.suite_id][event.kind] += 1
        case_events.setdefault(event.case_id, []).append(
            _diagnostic_event_to_dict(event)
        )
        if event.kind == "unexpected_error":
            unexpected_diagnostics.append(_diagnostic_event_to_dict(event))

    return {
        "aggregate": {
            "counts": aggregate_counts,
        },
        "suites": {
            suite_id: {"counts": counts}
            for suite_id, counts in sorted(suite_counts.items())
        },
        "cases": {case_id: case_events[case_id] for case_id in sorted(case_events)},
        "unexpected_diagnostics": unexpected_diagnostics,
    }


def evaluate_runtime(
    manifest: CalibrationManifest,
    runtime: EvaluationRuntime,
    *,
    fixture_manifest_path: Path | str = DEFAULT_FIXTURE_MANIFEST_PATH,
) -> PolicyEvaluationReport:
    outcomes: list[CaseOutcome] = []
    diagnostics: list[DiagnosticEvent] = []

    for suite in manifest.suites:
        for case in suite.cases:
            if isinstance(case, CandidateThresholdCase):
                outcomes.append(_evaluate_candidate_threshold_case(case, runtime))
            elif isinstance(case, ParseCase):
                try:
                    case_outcomes, case_diagnostics = _evaluate_parse_case(
                        case,
                        runtime,
                        fixture_manifest_path=fixture_manifest_path,
                    )
                except CalibrationCaseEvaluationError as exc:
                    diagnostics.extend(exc.diagnostics)
                    raise exc.original_exc from exc
                outcomes.extend(case_outcomes)
                diagnostics.extend(case_diagnostics)
            else:
                outcomes.append(_evaluate_merge_case(case, runtime))

    outcomes.sort(key=lambda outcome: outcome.outcome_id)
    case_outcomes = {outcome.outcome_id: outcome for outcome in outcomes}
    suite_summaries = {
        suite.suite_id: _build_summary(
            [outcome for outcome in outcomes if outcome.suite_id == suite.suite_id],
            threshold=runtime.threshold,
        )
        for suite in manifest.suites
    }
    return PolicyEvaluationReport(
        runtime=runtime,
        aggregate_summary=_build_summary(outcomes, threshold=runtime.threshold),
        suite_summaries=suite_summaries,
        case_outcomes=case_outcomes,
        source_mismatch_audit=_build_source_mismatch_audit(outcomes),
        diagnostics=tuple(diagnostics),
    )


def compare_policies(
    manifest: CalibrationManifest,
    *,
    baseline_policy: ConfidencePolicy,
    candidate_policy: ConfidencePolicy,
    shadow_policies: tuple[ShadowConsumerPolicy, ...] = (),
    fixture_manifest_path: Path | str = DEFAULT_FIXTURE_MANIFEST_PATH,
) -> PolicyComparisonReport:
    baseline_runtime = EvaluationRuntime(
        name=baseline_policy.name,
        confidence_policy=baseline_policy,
        threshold=manifest.threshold,
        strong_direct_threshold=baseline_policy.strong_direct_threshold,
    )
    candidate_runtime = EvaluationRuntime(
        name=candidate_policy.name,
        confidence_policy=candidate_policy,
        threshold=manifest.threshold,
        strong_direct_threshold=candidate_policy.strong_direct_threshold,
    )
    baseline = evaluate_runtime(
        manifest,
        baseline_runtime,
        fixture_manifest_path=fixture_manifest_path,
    )
    candidate = evaluate_runtime(
        manifest,
        candidate_runtime,
        fixture_manifest_path=fixture_manifest_path,
    )

    shadow_reports = {
        shadow.name: evaluate_runtime(
            manifest,
            EvaluationRuntime(
                name=shadow.name,
                confidence_policy=candidate_policy,
                threshold=shadow.threshold,
                strong_direct_threshold=shadow.strong_direct_threshold,
            ),
            fixture_manifest_path=fixture_manifest_path,
        )
        for shadow in shadow_policies
    }

    case_diffs = {
        outcome_id: CaseDiff(
            outcome_id=outcome_id,
            decision_type=candidate.case_outcomes[outcome_id].decision_type,
            suite_id=candidate.case_outcomes[outcome_id].suite_id,
            baseline=baseline.case_outcomes[outcome_id],
            candidate=candidate.case_outcomes[outcome_id],
        )
        for outcome_id in manifest.all_outcome_ids
    }

    suite_case_diffs: dict[str, dict[str, CaseDiff]] = defaultdict(dict)
    for outcome_id, case_diff in case_diffs.items():
        if (
            case_diff.baseline.outcome != case_diff.candidate.outcome
            or case_diff.baseline.correct != case_diff.candidate.correct
        ):
            suite_case_diffs[case_diff.suite_id][outcome_id] = case_diff

    threshold_sweep = {
        baseline_runtime.name: _build_threshold_sweep(
            manifest,
            policy=baseline_policy,
            strong_direct_threshold=baseline_runtime.strong_direct_threshold,
            fixture_manifest_path=fixture_manifest_path,
        ),
        candidate_runtime.name: _build_threshold_sweep(
            manifest,
            policy=candidate_policy,
            strong_direct_threshold=candidate_runtime.strong_direct_threshold,
            fixture_manifest_path=fixture_manifest_path,
        ),
    }

    return PolicyComparisonReport(
        manifest=manifest,
        baseline=baseline,
        candidate=candidate,
        shadow_policies=shadow_reports,
        case_diffs=case_diffs,
        threshold_sweep=threshold_sweep,
        invariant_checks=_build_invariant_checks(baseline_policy, candidate_policy),
        policy_diffs=_build_policy_diffs(baseline_policy, candidate_policy),
        suite_case_diffs={
            suite_id: dict(sorted(case_diffs.items()))
            for suite_id, case_diffs in sorted(suite_case_diffs.items())
        },
        coverage_audit=_build_coverage_audit(manifest),
    )


def render_calibration_report(report: PolicyComparisonReport) -> str:
    baseline = report.baseline.summary
    candidate = report.candidate.summary
    baseline_diagnostics = _build_diagnostics_export(report.baseline)
    candidate_diagnostics = _build_diagnostics_export(report.candidate)
    coverage_audit = report.coverage_audit or _build_coverage_audit(report.manifest)
    lines = [
        "# Extractor Confidence Calibration Evidence Pack",
        "",
        f"- Baseline policy: `{report.baseline.runtime.name}`",
        f"- Candidate policy: `{report.candidate.runtime.name}`",
        f"- Suites: `{', '.join(report.manifest.suite_ids)}`",
        f"- Reviewed threshold: `{report.manifest.threshold:.2f}`",
        "",
        "## Aggregate Operational Metrics",
        "",
        "| Policy | Accuracy | False Accepts | False Rejects | Survivors | Boundary Density | ECE | Brier |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| {report.baseline.runtime.name} | {baseline.operational_accuracy:.3f} | "
            f"{baseline.false_accept_count} | {baseline.false_reject_count} | "
            f"{baseline.survivor_count} | {baseline.boundary_density:.3f} | "
            f"{baseline.ece:.3f} | {baseline.brier_score:.3f} |"
        ),
        (
            f"| {report.candidate.runtime.name} | {candidate.operational_accuracy:.3f} | "
            f"{candidate.false_accept_count} | {candidate.false_reject_count} | "
            f"{candidate.survivor_count} | {candidate.boundary_density:.3f} | "
            f"{candidate.ece:.3f} | {candidate.brier_score:.3f} |"
        ),
        "",
        "## Per-Suite Summary",
        "",
        "| Suite | Baseline Accuracy | Candidate Accuracy | Baseline Survivors | Candidate Survivors |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for suite_id in report.manifest.suite_ids:
        baseline_suite = report.baseline.suite_summaries[suite_id]
        candidate_suite = report.candidate.suite_summaries[suite_id]
        lines.append(
            f"| {suite_id} | {baseline_suite.operational_accuracy:.3f} | "
            f"{candidate_suite.operational_accuracy:.3f} | "
            f"{baseline_suite.survivor_count} | {candidate_suite.survivor_count} |"
        )

    lines.extend(["", "## Coverage Audit", ""])
    for scope in (*report.manifest.suite_ids, "all"):
        lines.append(
            f"- `{scope}` missing required surfaces: "
            f"{', '.join(coverage_audit.missing_required_surfaces[scope]) or 'none'}"
        )
        lines.append(
            f"- `{scope}` under-anchored required surfaces: "
            f"{', '.join(coverage_audit.underanchored_required_surfaces[scope]) or 'none'}"
        )

    lines.extend(["", "## Source Mismatch Audit", ""])
    lines.append(
        f"- Baseline advisory mismatches: {', '.join(report.baseline.source_mismatch_audit.advisory_mismatches) or 'none'}"
    )
    lines.append(
        f"- Baseline critical mismatches: {', '.join(report.baseline.source_mismatch_audit.critical_mismatches) or 'none'}"
    )
    lines.append(
        f"- Candidate advisory mismatches: {', '.join(report.candidate.source_mismatch_audit.advisory_mismatches) or 'none'}"
    )
    lines.append(
        f"- Candidate critical mismatches: {', '.join(report.candidate.source_mismatch_audit.critical_mismatches) or 'none'}"
    )

    lines.extend(["", "## Diagnostics Summary", ""])
    lines.append(
        "- Baseline diagnostics: "
        + ", ".join(
            f"{kind}={baseline_diagnostics['aggregate']['counts'][kind]}"
            for kind in DIAGNOSTIC_KINDS
        )
    )
    lines.append(
        "- Candidate diagnostics: "
        + ", ".join(
            f"{kind}={candidate_diagnostics['aggregate']['counts'][kind]}"
            for kind in DIAGNOSTIC_KINDS
        )
    )
    if baseline_diagnostics["cases"] or candidate_diagnostics["cases"]:
        lines.extend(["", "## Notable Noisy Cases", ""])
        if baseline_diagnostics["cases"]:
            lines.append("### Baseline")
            lines.append("")
            for case_id, events in baseline_diagnostics["cases"].items():
                lines.append(
                    f"- `{case_id}`: "
                    + ", ".join(
                        f"{event['sequence']}:{event['kind']}" for event in events
                    )
                )
            lines.append("")
        if candidate_diagnostics["cases"]:
            lines.append("### Candidate")
            lines.append("")
            for case_id, events in candidate_diagnostics["cases"].items():
                lines.append(
                    f"- `{case_id}`: "
                    + ", ".join(
                        f"{event['sequence']}:{event['kind']}" for event in events
                    )
                )
            lines.append("")

    lines.extend(["", "## Policy Diffs", ""])
    if not report.policy_diffs:
        lines.append("- No runtime calibration deltas were detected.")
    else:
        for diff in report.policy_diffs:
            lines.append(
                f"- `{diff.setting}`: `{diff.baseline:.2f}` -> `{diff.candidate:.2f}`"
            )

    lines.extend(["", "## Trust-Order Invariant Checks", ""])
    for check in report.invariant_checks:
        status = "PASS" if check.passed else "FAIL"
        lines.append(f"- `{status}` {check.name}: {check.details}")

    lines.extend(["", "## Threshold Sweep", ""])
    for runtime_name, sweep_points in report.threshold_sweep.items():
        lines.append(f"### `{runtime_name}`")
        lines.append("")
        lines.append(
            "| Threshold | Accuracy | False Accepts | False Rejects | Survivors | Acceptance Rate |"
        )
        lines.append("| ---: | ---: | ---: | ---: | ---: | ---: |")
        for point in sweep_points:
            lines.append(
                f"| {point.threshold:.2f} | {point.operational_accuracy:.3f} | "
                f"{point.false_accept_count} | {point.false_reject_count} | "
                f"{point.survivor_count} | {point.acceptance_rate:.3f} |"
            )
        lines.append("")

    lines.extend(["## Notable Case Diffs", ""])
    if not report.suite_case_diffs:
        lines.append("- No decision flips between baseline and candidate policies.")
    else:
        for suite_id, suite_diffs in report.suite_case_diffs.items():
            lines.append(f"### `{suite_id}`")
            lines.append("")
            for outcome_id, case_diff in suite_diffs.items():
                lines.append(
                    f"- `{outcome_id}` ({case_diff.decision_type}): "
                    f"`{case_diff.baseline.outcome}` -> `{case_diff.candidate.outcome}` "
                    f"(correct `{case_diff.baseline.correct}` -> `{case_diff.candidate.correct}`)"
                )
            lines.append("")

    if report.shadow_policies:
        lines.extend(["## Shadow Consumer Diffs", ""])
        for name, shadow_report in report.shadow_policies.items():
            lines.append(
                f"- `{name}` accuracy={shadow_report.summary.operational_accuracy:.3f}, "
                f"survivors={shadow_report.summary.survivor_count}, "
                f"false_accepts={shadow_report.summary.false_accept_count}, "
                f"false_rejects={shadow_report.summary.false_reject_count}"
            )

    return "\n".join(lines)


def report_to_dict(report: PolicyComparisonReport) -> dict[str, Any]:
    def _summary_to_dict(summary: EvaluationSummary) -> dict[str, Any]:
        return {
            "total_cases": summary.total_cases,
            "correct_cases": summary.correct_cases,
            "operational_accuracy": round(summary.operational_accuracy, 6),
            "false_accept_count": summary.false_accept_count,
            "false_reject_count": summary.false_reject_count,
            "survivor_count": summary.survivor_count,
            "acceptance_rate": round(summary.acceptance_rate, 6),
            "boundary_density": round(summary.boundary_density, 6),
            "mean_confidence": round(summary.mean_confidence, 6),
            "brier_score": round(summary.brier_score, 6),
            "ece": round(summary.ece, 6),
            "decision_surface_counts": dict(summary.decision_surface_counts),
            "reliability_bins": [
                {
                    "lower": bucket.lower,
                    "upper": bucket.upper,
                    "count": bucket.count,
                    "mean_confidence": round(bucket.mean_confidence, 6),
                    "accuracy": round(bucket.accuracy, 6),
                }
                for bucket in summary.reliability_bins
            ],
        }

    def _source_mismatch_audit_to_dict(
        audit: SourceMismatchAudit,
    ) -> dict[str, list[str]]:
        return {
            "advisory_mismatches": list(audit.advisory_mismatches),
            "critical_mismatches": list(audit.critical_mismatches),
        }

    def _outcome_to_dict(outcome: CaseOutcome) -> dict[str, Any]:
        return {
            "case_id": outcome.case_id,
            "suite_id": outcome.suite_id,
            "suite_tier": outcome.suite_tier,
            "metric_key": outcome.metric_key,
            "decision_surface": outcome.decision_surface,
            "risk_tags": list(outcome.risk_tags),
            "anchor": outcome.anchor,
            "fixture_ref": outcome.fixture_ref,
            "decision_type": outcome.decision_type,
            "correct": outcome.correct,
            "outcome": outcome.outcome,
            "expected_outcome": outcome.expected_outcome,
            "confidence": round(outcome.confidence, 6),
            "source": outcome.source,
            "source_strictness": outcome.source_strictness,
            "expected_source": outcome.expected_source,
            "source_mismatch": outcome.source_mismatch,
            "authoritative_override": outcome.authoritative_override,
            "expected_authoritative_override": outcome.expected_authoritative_override,
            "authoritative_override_mismatch": outcome.authoritative_override_mismatch,
            "reason_code": outcome.reason_code,
            "expected_reason_code": outcome.expected_reason_code,
            "reason_code_mismatch": outcome.reason_code_mismatch,
            "survived": outcome.survived,
            "false_accept": outcome.false_accept,
            "false_reject": outcome.false_reject,
        }

    def _evaluation_report_to_dict(
        report_obj: PolicyEvaluationReport,
    ) -> dict[str, Any]:
        return {
            "runtime": report_obj.runtime.name,
            "aggregate": {
                "summary": _summary_to_dict(report_obj.aggregate_summary),
            },
            "suites": {
                suite_id: {
                    "summary": _summary_to_dict(summary),
                }
                for suite_id, summary in sorted(report_obj.suite_summaries.items())
            },
            "source_mismatch_audit": _source_mismatch_audit_to_dict(
                report_obj.source_mismatch_audit
            ),
            "diagnostics": _build_diagnostics_export(report_obj),
            "case_outcomes": {
                outcome_id: _outcome_to_dict(report_obj.case_outcomes[outcome_id])
                for outcome_id in sorted(report_obj.case_outcomes)
            },
        }

    coverage_audit = report.coverage_audit or _build_coverage_audit(report.manifest)
    return {
        "manifest": {
            "version": report.manifest.version,
            "threshold": report.manifest.threshold,
            "suite_ids": list(report.manifest.suite_ids),
        },
        "coverage_audit": {
            "required_surfaces": list(coverage_audit.required_surfaces),
            "expansion_priority_surfaces": list(
                coverage_audit.expansion_priority_surfaces
            ),
            "present_surfaces": {
                scope: list(surfaces)
                for scope, surfaces in sorted(coverage_audit.present_surfaces.items())
            },
            "missing_required_surfaces": {
                scope: list(surfaces)
                for scope, surfaces in sorted(
                    coverage_audit.missing_required_surfaces.items()
                )
            },
            "anchor_surfaces": {
                scope: list(surfaces)
                for scope, surfaces in sorted(coverage_audit.anchor_surfaces.items())
            },
            "real_fixture_anchor_surfaces": {
                scope: list(surfaces)
                for scope, surfaces in sorted(
                    coverage_audit.real_fixture_anchor_surfaces.items()
                )
            },
            "underanchored_required_surfaces": {
                scope: list(surfaces)
                for scope, surfaces in sorted(
                    coverage_audit.underanchored_required_surfaces.items()
                )
            },
            "risk_tag_counts": {
                scope: dict(sorted(tag_counts.items()))
                for scope, tag_counts in sorted(coverage_audit.risk_tag_counts.items())
            },
        },
        "baseline": _evaluation_report_to_dict(report.baseline),
        "candidate": _evaluation_report_to_dict(report.candidate),
        "shadow_policies": {
            name: _evaluation_report_to_dict(shadow_report)
            for name, shadow_report in sorted(report.shadow_policies.items())
        },
        "threshold_sweep": {
            runtime_name: [
                {
                    "threshold": point.threshold,
                    "operational_accuracy": round(point.operational_accuracy, 6),
                    "false_accept_count": point.false_accept_count,
                    "false_reject_count": point.false_reject_count,
                    "survivor_count": point.survivor_count,
                    "acceptance_rate": round(point.acceptance_rate, 6),
                }
                for point in sweep_points
            ]
            for runtime_name, sweep_points in sorted(report.threshold_sweep.items())
        },
        "invariant_checks": [
            {
                "name": check.name,
                "passed": check.passed,
                "details": check.details,
            }
            for check in report.invariant_checks
        ],
        "policy_diffs": [
            {
                "setting": diff.setting,
                "baseline": round(diff.baseline, 6),
                "candidate": round(diff.candidate, 6),
            }
            for diff in report.policy_diffs
        ],
        "case_diffs": {
            outcome_id: {
                "decision_type": case_diff.decision_type,
                "suite_id": case_diff.suite_id,
                "baseline": _outcome_to_dict(case_diff.baseline),
                "candidate": _outcome_to_dict(case_diff.candidate),
            }
            for outcome_id, case_diff in sorted(report.case_diffs.items())
            if case_diff.baseline.outcome != case_diff.candidate.outcome
            or case_diff.baseline.correct != case_diff.candidate.correct
        },
        "suite_case_diffs": {
            suite_id: {
                outcome_id: {
                    "decision_type": case_diff.decision_type,
                    "baseline": _outcome_to_dict(case_diff.baseline),
                    "candidate": _outcome_to_dict(case_diff.candidate),
                }
                for outcome_id, case_diff in sorted(case_diffs.items())
            }
            for suite_id, case_diffs in sorted(report.suite_case_diffs.items())
        },
    }


__all__ = [
    "CalibrationManifest",
    "CalibrationSuite",
    "CandidateDescriptor",
    "CandidateThresholdCase",
    "CaseDiff",
    "CaseOutcome",
    "CoverageAudit",
    "DEFAULT_FIXTURE_MANIFEST_PATH",
    "DEFAULT_MANIFEST_PATH",
    "DEFAULT_SHADOW_POLICIES",
    "DECISION_SURFACES",
    "EXPANSION_PRIORITY_SURFACES",
    "EvaluationRuntime",
    "InvariantCheck",
    "MergeCase",
    "MetricExpectation",
    "ParseCase",
    "PolicyComparisonReport",
    "PolicyEvaluationReport",
    "PolicySettingDiff",
    "REQUIRED_DECISION_SURFACES",
    "RISK_TAG_VOCABULARY",
    "ResolvedFixture",
    "ShadowConsumerPolicy",
    "ThresholdSweepPoint",
    "compare_policies",
    "evaluate_runtime",
    "load_calibration_manifest",
    "render_calibration_report",
    "report_to_dict",
    "resolve_fixture_ref",
]
