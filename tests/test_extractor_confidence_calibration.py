from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.analysis.extractor import semantics


def _manifest_path() -> Path:
    return Path(__file__).parent / "data" / "extractor_confidence_calibration.json"


def test_baseline_policy_preserves_current_weak_text_keyword_score_and_runtime_is_more_conservative() -> (
    None
):
    from src.analysis.extractor.confidence_policy import (
        BASELINE_RUNTIME_CONFIDENCE_POLICY,
        RUNTIME_CONFIDENCE_POLICY,
        build_policy_decision_log,
    )

    profile_key = ("text", "keyword_match", "direct")
    baseline = build_policy_decision_log(
        BASELINE_RUNTIME_CONFIDENCE_POLICY,
        profile_key,
        metric_key="revenue",
        candidate_quality=50,
        signal_flags=[],
        conflict_count=0,
        postprocess_state="none",
        authoritative_override=False,
        reason_code=None,
    )
    calibrated = build_policy_decision_log(
        RUNTIME_CONFIDENCE_POLICY,
        profile_key,
        metric_key="revenue",
        candidate_quality=50,
        signal_flags=[],
        conflict_count=0,
        postprocess_state="none",
        authoritative_override=False,
        reason_code=None,
    )
    runtime = semantics.build_decision_log(
        profile_key,
        metric_key="revenue",
        candidate_quality=50,
        signal_flags=[],
        conflict_count=0,
        postprocess_state="none",
        authoritative_override=False,
        reason_code=None,
    )

    assert baseline.final_confidence == 0.5
    assert calibrated.final_confidence == pytest.approx(0.46)
    assert runtime.final_confidence == calibrated.final_confidence


def test_compare_policies_reports_operational_improvement_on_frozen_manifest() -> None:
    from src.analysis.extractor import calibration
    from src.analysis.extractor.confidence_policy import (
        BASELINE_RUNTIME_CONFIDENCE_POLICY,
        RUNTIME_CONFIDENCE_POLICY,
    )

    manifest = calibration.load_calibration_manifest(_manifest_path())
    report = calibration.compare_policies(
        manifest,
        baseline_policy=BASELINE_RUNTIME_CONFIDENCE_POLICY,
        candidate_policy=RUNTIME_CONFIDENCE_POLICY,
        shadow_policies=calibration.DEFAULT_SHADOW_POLICIES,
    )

    assert report.baseline.summary.total_cases == report.candidate.summary.total_cases
    assert (
        report.candidate.summary.operational_accuracy
        > report.baseline.summary.operational_accuracy
    )
    assert (
        report.candidate.summary.false_accept_count
        < report.baseline.summary.false_accept_count
    )
    assert "shadow_relaxed_consumer" in report.shadow_policies


def test_merge_case_flips_from_fallback_to_llm_under_calibrated_policy() -> None:
    from src.analysis.extractor import calibration
    from src.analysis.extractor.confidence_policy import (
        BASELINE_RUNTIME_CONFIDENCE_POLICY,
        RUNTIME_CONFIDENCE_POLICY,
    )

    manifest = calibration.load_calibration_manifest(_manifest_path())
    report = calibration.compare_policies(
        manifest,
        baseline_policy=BASELINE_RUNTIME_CONFIDENCE_POLICY,
        candidate_policy=RUNTIME_CONFIDENCE_POLICY,
    )

    case_diff = report.case_diffs["llm_replaces_weak_text_keyword_fallback"]

    assert case_diff.decision_type == "merge"
    assert case_diff.baseline.outcome == "fallback"
    assert case_diff.candidate.outcome == "llm"


def test_shadow_policy_analysis_does_not_mutate_runtime_policy() -> None:
    from src.analysis.extractor import calibration
    from src.analysis.extractor.confidence_policy import (
        BASELINE_RUNTIME_CONFIDENCE_POLICY,
        RUNTIME_CONFIDENCE_POLICY,
    )

    profile_key = ("text", "keyword_match", "direct")
    before = semantics.build_decision_log(
        profile_key,
        metric_key="revenue",
        candidate_quality=50,
        signal_flags=[],
        conflict_count=0,
        postprocess_state="none",
        authoritative_override=False,
        reason_code=None,
    )

    manifest = calibration.load_calibration_manifest(_manifest_path())
    calibration.compare_policies(
        manifest,
        baseline_policy=BASELINE_RUNTIME_CONFIDENCE_POLICY,
        candidate_policy=RUNTIME_CONFIDENCE_POLICY,
        shadow_policies=calibration.DEFAULT_SHADOW_POLICIES,
    )

    after = semantics.build_decision_log(
        profile_key,
        metric_key="revenue",
        candidate_quality=50,
        signal_flags=[],
        conflict_count=0,
        postprocess_state="none",
        authoritative_override=False,
        reason_code=None,
    )

    assert before.final_confidence == after.final_confidence


def test_report_rendering_and_machine_readable_export_include_candidate_metrics() -> (
    None
):
    from src.analysis.extractor import calibration
    from src.analysis.extractor.confidence_policy import (
        BASELINE_RUNTIME_CONFIDENCE_POLICY,
        RUNTIME_CONFIDENCE_POLICY,
    )

    manifest = calibration.load_calibration_manifest(_manifest_path())
    report = calibration.compare_policies(
        manifest,
        baseline_policy=BASELINE_RUNTIME_CONFIDENCE_POLICY,
        candidate_policy=RUNTIME_CONFIDENCE_POLICY,
        shadow_policies=calibration.DEFAULT_SHADOW_POLICIES,
    )

    rendered = calibration.render_calibration_report(report)
    exported = calibration.report_to_dict(report)

    assert report.candidate.runtime.name in rendered
    assert "Operational Metrics" in rendered
    assert "Threshold Sweep" in rendered
    assert (
        exported["candidate"]["summary"]["operational_accuracy"]
        > exported["baseline"]["summary"]["operational_accuracy"]
    )
    assert exported["invariant_checks"]
    assert exported["threshold_sweep"]


def test_threshold_sweep_keeps_survivor_count_monotonic() -> None:
    from src.analysis.extractor import calibration
    from src.analysis.extractor.confidence_policy import (
        BASELINE_RUNTIME_CONFIDENCE_POLICY,
        RUNTIME_CONFIDENCE_POLICY,
    )

    manifest = calibration.load_calibration_manifest(_manifest_path())
    report = calibration.compare_policies(
        manifest,
        baseline_policy=BASELINE_RUNTIME_CONFIDENCE_POLICY,
        candidate_policy=RUNTIME_CONFIDENCE_POLICY,
    )

    for sweep_points in report.threshold_sweep.values():
        survivor_counts = [point.survivor_count for point in sweep_points]
        assert survivor_counts == sorted(survivor_counts, reverse=True)


def test_manifest_validation_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    from src.analysis.extractor import calibration

    manifest_path = tmp_path / "invalid_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "threshold": 0.5,
                "cases": [
                    {
                        "id": "duplicate_case",
                        "kind": "candidate_threshold",
                        "metric_key": "revenue",
                        "candidate": {
                            "value": 100.0,
                            "match_type": "table",
                            "is_exact": True,
                        },
                        "expected": {"survives": True},
                    },
                    {
                        "id": "duplicate_case",
                        "kind": "candidate_threshold",
                        "metric_key": "revenue",
                        "candidate": {
                            "value": 100.0,
                            "match_type": "table",
                            "is_exact": True,
                        },
                        "expected": {"survives": True},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate calibration case id"):
        calibration.load_calibration_manifest(manifest_path)
