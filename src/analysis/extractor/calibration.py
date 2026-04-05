from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from .confidence_policy import ConfidencePolicy
from .pipeline import build_extractor_trace, build_metadata_from_trace
from .ranking import apply_confidence_filter, build_metadata_from_candidate
from .runtime_decisions import should_prefer_llm_metric
from .types import ExtractionMetadata, RawMetricCandidate

DEFAULT_MANIFEST_PATH: Final = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "data"
    / "extractor_confidence_calibration.json"
)
SWEEP_OFFSETS: Final[tuple[float, ...]] = (-0.10, -0.05, 0.0, 0.05, 0.10)
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
    source_decision_critical: bool = False


@dataclass(frozen=True, slots=True)
class CandidateThresholdCase:
    case_id: str
    metric_key: str
    candidate: CandidateDescriptor
    expected: MetricExpectation


@dataclass(frozen=True, slots=True)
class ParseCase:
    case_id: str
    tables: list
    text: str
    metric_key: str
    expected: MetricExpectation


@dataclass(frozen=True, slots=True)
class MergeCase:
    case_id: str
    metric_key: str
    llm_metadata: ExtractionMetadata
    expected_winner: str
    fallback_candidate: CandidateDescriptor | None = None
    fallback_metadata: ExtractionMetadata | None = None


@dataclass(frozen=True, slots=True)
class CalibrationManifest:
    version: int
    threshold: float
    threshold_cases: tuple[CandidateThresholdCase | ParseCase, ...]
    merge_cases: tuple[MergeCase, ...]

    @property
    def all_case_ids(self) -> tuple[str, ...]:
        threshold_ids = [case.case_id for case in self.threshold_cases]
        merge_ids = [case.case_id for case in self.merge_cases]
        return tuple(threshold_ids + merge_ids)


@dataclass(frozen=True, slots=True)
class EvaluationRuntime:
    name: str
    confidence_policy: ConfidencePolicy
    threshold: float
    strong_direct_threshold: float | None = None


@dataclass(frozen=True, slots=True)
class CaseOutcome:
    case_id: str
    decision_type: str
    correct: bool
    outcome: str
    expected_outcome: str
    confidence: float
    source: str | None
    survived: bool | None
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
class PolicyEvaluationReport:
    runtime: EvaluationRuntime
    summary: EvaluationSummary
    case_outcomes: dict[str, CaseOutcome]


@dataclass(frozen=True, slots=True)
class CaseDiff:
    case_id: str
    decision_type: str
    baseline: CaseOutcome
    candidate: CaseOutcome


@dataclass(frozen=True, slots=True)
class PolicyComparisonReport:
    manifest: CalibrationManifest
    baseline: PolicyEvaluationReport
    candidate: PolicyEvaluationReport
    shadow_policies: dict[str, PolicyEvaluationReport]
    case_diffs: dict[str, CaseDiff]
    threshold_sweep: dict[str, tuple["ThresholdSweepPoint", ...]]
    invariant_checks: tuple["InvariantCheck", ...]
    policy_diffs: tuple["PolicySettingDiff", ...]


@dataclass(frozen=True, slots=True)
class ShadowConsumerPolicy:
    name: str
    threshold: float
    strong_direct_threshold: float


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


DEFAULT_SHADOW_POLICIES: Final[tuple[ShadowConsumerPolicy, ...]] = (
    ShadowConsumerPolicy(
        name="shadow_relaxed_consumer",
        threshold=0.5,
        strong_direct_threshold=0.65,
    ),
)


def _load_json(path: Path) -> dict[str, Any]:
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
    source_decision_critical = bool(payload.get("source_decision_critical", False))
    if source_decision_critical and not expected_source:
        raise ValueError("source_decision_critical requires expected_source")
    return MetricExpectation(
        survives=bool(payload["survives"]),
        value=payload.get("value"),
        tolerance=float(payload.get("tolerance", 0.0)),
        expected_source=expected_source,
        source_decision_critical=source_decision_critical,
    )


def load_calibration_manifest(
    path: Path | str = DEFAULT_MANIFEST_PATH,
) -> CalibrationManifest:
    manifest_path = Path(path)
    payload = _load_json(manifest_path)
    version = int(payload["version"])
    if version != 1:
        raise ValueError(f"Unsupported calibration manifest version: {version}")

    threshold_cases: list[CandidateThresholdCase | ParseCase] = []
    merge_cases: list[MergeCase] = []
    seen_ids: set[str] = set()

    for raw_case in payload.get("cases", []):
        case_id = raw_case["id"]
        if case_id in seen_ids:
            raise ValueError(f"Duplicate calibration case id: {case_id}")
        seen_ids.add(case_id)

        kind = raw_case["kind"]
        if kind == "candidate_threshold":
            threshold_cases.append(
                CandidateThresholdCase(
                    case_id=case_id,
                    metric_key=raw_case["metric_key"],
                    candidate=_build_candidate_descriptor(raw_case["candidate"]),
                    expected=_build_expectation(raw_case["expected"]),
                )
            )
            continue

        if kind == "parse":
            expectations = raw_case["expectations"]
            if len(expectations) != 1:
                raise ValueError(
                    "Parse calibration cases currently support exactly one metric expectation"
                )
            metric_key, expectation_payload = next(iter(expectations.items()))
            threshold_cases.append(
                ParseCase(
                    case_id=case_id,
                    tables=list(raw_case.get("tables", [])),
                    text=raw_case.get("text", ""),
                    metric_key=metric_key,
                    expected=_build_expectation(expectation_payload),
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
            merge_cases.append(
                MergeCase(
                    case_id=case_id,
                    metric_key=raw_case["metric_key"],
                    llm_metadata=_build_metadata(raw_case["llm_metadata"]),
                    expected_winner=raw_case["expected"]["winner"],
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

    return CalibrationManifest(
        version=version,
        threshold=float(payload.get("threshold", 0.5)),
        threshold_cases=tuple(threshold_cases),
        merge_cases=tuple(merge_cases),
    )


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
    case_id: str,
    decision_type: str,
    metric_key: str,
    metadata: ExtractionMetadata,
    expectation: MetricExpectation,
    *,
    threshold: float,
) -> CaseOutcome:
    filtered, _ = apply_confidence_filter({metric_key: metadata}, threshold=threshold)
    survives = filtered[metric_key] is not None
    actual_source = metadata.source if metadata.value is not None else None
    correct = survives == expectation.survives
    if (
        correct
        and expectation.source_decision_critical
        and survives
        and expectation.expected_source is not None
    ):
        correct = actual_source == expectation.expected_source
    if correct and expectation.value is not None and survives:
        correct = (
            abs((metadata.value or 0.0) - expectation.value) <= expectation.tolerance
        )

    expected_outcome = (
        f"survive:{expectation.expected_source}"
        if expectation.survives and expectation.source_decision_critical
        else ("survive" if expectation.survives else "absent")
    )
    outcome = (
        f"survive:{actual_source}"
        if survives and actual_source is not None
        else "absent"
    )
    return CaseOutcome(
        case_id=case_id,
        decision_type=decision_type,
        correct=correct,
        outcome=outcome,
        expected_outcome=expected_outcome,
        confidence=metadata.confidence,
        source=actual_source,
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
        case.case_id,
        "threshold",
        case.metric_key,
        metadata,
        case.expected,
        threshold=runtime.threshold,
    )


def _evaluate_parse_case(
    case: ParseCase,
    runtime: EvaluationRuntime,
) -> CaseOutcome:
    trace = build_extractor_trace(case.tables, case.text)
    metadata, _ = build_metadata_from_trace(
        trace,
        confidence_policy=runtime.confidence_policy,
        include_decision_logs=True,
    )
    return _evaluate_threshold_expectation(
        case.case_id,
        "winner",
        case.metric_key,
        metadata[case.metric_key],
        case.expected,
        threshold=runtime.threshold,
    )


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
    return CaseOutcome(
        case_id=case.case_id,
        decision_type="merge",
        correct=actual_winner == case.expected_winner,
        outcome=actual_winner,
        expected_outcome=case.expected_winner,
        confidence=confidence,
        source=source,
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


def _build_summary(outcomes: list[CaseOutcome]) -> EvaluationSummary:
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
        sum(1 for outcome in outcomes if abs(outcome.confidence - 0.5) <= 0.05)
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
    decision_surface_counts = {
        "threshold": sum(
            1 for outcome in outcomes if outcome.decision_type == "threshold"
        ),
        "winner": sum(1 for outcome in outcomes if outcome.decision_type == "winner"),
        "merge": sum(1 for outcome in outcomes if outcome.decision_type == "merge"),
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


def _build_threshold_sweep(
    manifest: CalibrationManifest,
    *,
    policy: ConfidencePolicy,
    strong_direct_threshold: float | None,
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
        summary = evaluate_runtime(manifest, runtime).summary
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


def evaluate_runtime(
    manifest: CalibrationManifest,
    runtime: EvaluationRuntime,
) -> PolicyEvaluationReport:
    outcomes: list[CaseOutcome] = []

    for case in manifest.threshold_cases:
        if isinstance(case, CandidateThresholdCase):
            outcomes.append(_evaluate_candidate_threshold_case(case, runtime))
        else:
            outcomes.append(_evaluate_parse_case(case, runtime))

    for case in manifest.merge_cases:
        outcomes.append(_evaluate_merge_case(case, runtime))

    case_outcomes = {outcome.case_id: outcome for outcome in outcomes}
    return PolicyEvaluationReport(
        runtime=runtime,
        summary=_build_summary(outcomes),
        case_outcomes=case_outcomes,
    )


def compare_policies(
    manifest: CalibrationManifest,
    *,
    baseline_policy: ConfidencePolicy,
    candidate_policy: ConfidencePolicy,
    shadow_policies: tuple[ShadowConsumerPolicy, ...] = (),
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
    baseline = evaluate_runtime(manifest, baseline_runtime)
    candidate = evaluate_runtime(manifest, candidate_runtime)

    shadow_reports = {
        shadow.name: evaluate_runtime(
            manifest,
            EvaluationRuntime(
                name=shadow.name,
                confidence_policy=candidate_policy,
                threshold=shadow.threshold,
                strong_direct_threshold=shadow.strong_direct_threshold,
            ),
        )
        for shadow in shadow_policies
    }

    case_diffs = {
        case_id: CaseDiff(
            case_id=case_id,
            decision_type=candidate.case_outcomes[case_id].decision_type,
            baseline=baseline.case_outcomes[case_id],
            candidate=candidate.case_outcomes[case_id],
        )
        for case_id in manifest.all_case_ids
    }
    threshold_sweep = {
        baseline_runtime.name: _build_threshold_sweep(
            manifest,
            policy=baseline_policy,
            strong_direct_threshold=baseline_runtime.strong_direct_threshold,
        ),
        candidate_runtime.name: _build_threshold_sweep(
            manifest,
            policy=candidate_policy,
            strong_direct_threshold=candidate_runtime.strong_direct_threshold,
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
    )


def render_calibration_report(report: PolicyComparisonReport) -> str:
    baseline = report.baseline.summary
    candidate = report.candidate.summary
    coverage_shift = candidate.survivor_count - baseline.survivor_count
    lines = [
        "# Extractor Confidence Calibration Evidence Pack",
        "",
        f"- Baseline policy: `{report.baseline.runtime.name}`",
        f"- Candidate policy: `{report.candidate.runtime.name}`",
        f"- Total decisions: `{candidate.total_cases}`",
        f"- Reviewed threshold: `{report.manifest.threshold:.2f}`",
        (
            "- Decision surface counts: "
            f"`threshold={candidate.decision_surface_counts['threshold']}`, "
            f"`winner={candidate.decision_surface_counts['winner']}`, "
            f"`merge={candidate.decision_surface_counts['merge']}`"
        ),
        "",
        "## Operational Metrics",
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
        "## Decision Quality Guardrails",
        "",
        f"- Survivor count shift: `{coverage_shift:+d}`",
        f"- Acceptance rate shift: `{candidate.acceptance_rate - baseline.acceptance_rate:+.3f}`",
        f"- Mean confidence shift: `{candidate.mean_confidence - baseline.mean_confidence:+.3f}`",
        f"- Boundary density shift: `{candidate.boundary_density - baseline.boundary_density:+.3f}`",
        "",
        "## Policy Diffs",
        "",
    ]

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
    flipped_cases = [
        case_diff
        for case_diff in report.case_diffs.values()
        if case_diff.baseline.outcome != case_diff.candidate.outcome
        or case_diff.baseline.correct != case_diff.candidate.correct
    ]
    if not flipped_cases:
        lines.append("- No decision flips between baseline and candidate policies.")
    else:
        for case_diff in flipped_cases:
            lines.append(
                f"- `{case_diff.case_id}` ({case_diff.decision_type}): "
                f"`{case_diff.baseline.outcome}` -> `{case_diff.candidate.outcome}` "
                f"(correct `{case_diff.baseline.correct}` -> `{case_diff.candidate.correct}`)"
            )

    if report.shadow_policies:
        lines.extend(["", "## Shadow Consumer Diffs", ""])
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

    def _outcome_to_dict(outcome: CaseOutcome) -> dict[str, Any]:
        return {
            "decision_type": outcome.decision_type,
            "correct": outcome.correct,
            "outcome": outcome.outcome,
            "expected_outcome": outcome.expected_outcome,
            "confidence": round(outcome.confidence, 6),
            "source": outcome.source,
            "survived": outcome.survived,
            "false_accept": outcome.false_accept,
            "false_reject": outcome.false_reject,
        }

    return {
        "baseline": {
            "runtime": report.baseline.runtime.name,
            "summary": _summary_to_dict(report.baseline.summary),
            "case_outcomes": {
                key: _outcome_to_dict(value)
                for key, value in report.baseline.case_outcomes.items()
            },
        },
        "candidate": {
            "runtime": report.candidate.runtime.name,
            "summary": _summary_to_dict(report.candidate.summary),
            "case_outcomes": {
                key: _outcome_to_dict(value)
                for key, value in report.candidate.case_outcomes.items()
            },
        },
        "shadow_policies": {
            name: {
                "runtime": value.runtime.name,
                "summary": _summary_to_dict(value.summary),
            }
            for name, value in report.shadow_policies.items()
        },
        "threshold_sweep": {
            name: [
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
            for name, sweep_points in report.threshold_sweep.items()
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
            case_id: {
                "decision_type": case_diff.decision_type,
                "baseline": _outcome_to_dict(case_diff.baseline),
                "candidate": _outcome_to_dict(case_diff.candidate),
            }
            for case_id, case_diff in report.case_diffs.items()
            if case_diff.baseline.outcome != case_diff.candidate.outcome
            or case_diff.baseline.correct != case_diff.candidate.correct
        },
    }


__all__ = [
    "CalibrationManifest",
    "CandidateDescriptor",
    "CandidateThresholdCase",
    "DEFAULT_MANIFEST_PATH",
    "DEFAULT_SHADOW_POLICIES",
    "EvaluationRuntime",
    "MergeCase",
    "MetricExpectation",
    "ParseCase",
    "PolicySettingDiff",
    "PolicyComparisonReport",
    "PolicyEvaluationReport",
    "ShadowConsumerPolicy",
    "ThresholdSweepPoint",
    "InvariantCheck",
    "compare_policies",
    "evaluate_runtime",
    "load_calibration_manifest",
    "render_calibration_report",
    "report_to_dict",
]
