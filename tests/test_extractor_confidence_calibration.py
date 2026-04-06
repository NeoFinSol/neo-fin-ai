from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.analysis.extractor import semantics


def _manifest_root() -> Path:
    return Path(__file__).parent / "data" / "extractor_confidence_calibration"


def _write_suite(
    root: Path,
    *,
    suite_id: str,
    suite_tier: str,
    cases: list[dict],
    threshold: float = 0.5,
    version: int = 2,
) -> Path:
    path = root / f"{suite_id}.json"
    path.write_text(
        json.dumps(
            {
                "version": version,
                "threshold": threshold,
                "suite_id": suite_id,
                "suite_tier": suite_tier,
                "cases": cases,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _candidate_payload(
    *,
    value: float = 100.0,
    source: str = "text",
    match_semantics: str = "code_match",
    inference_mode: str = "direct",
    candidate_quality: int = 95,
    is_exact: bool = False,
) -> dict:
    return {
        "value": value,
        "match_type": "text_regex",
        "is_exact": is_exact,
        "candidate_quality": candidate_quality,
        "source": source,
        "match_semantics": match_semantics,
        "inference_mode": inference_mode,
        "signal_flags": [],
    }


def test_default_manifest_directory_contains_fast_and_gated_suites() -> None:
    from src.analysis.extractor import calibration

    manifest = calibration.load_calibration_manifest(_manifest_root(), suite="all")

    assert tuple(suite.suite_id for suite in manifest.suites) == ("fast", "gated")
    assert manifest.threshold == 0.5
    assert "fast_inline_winner_pair" in manifest.all_case_ids
    assert "gated_corvel_parse_anchor" in manifest.all_case_ids


def test_loader_rejects_duplicate_case_ids_across_suites(tmp_path: Path) -> None:
    from src.analysis.extractor import calibration

    _write_suite(
        tmp_path,
        suite_id="fast",
        suite_tier="fast",
        cases=[
            {
                "case_id": "duplicate_case",
                "kind": "candidate_threshold",
                "decision_surface": "threshold_boundary",
                "risk_tags": ["low_confidence"],
                "anchor": False,
                "metric_key": "revenue",
                "candidate": _candidate_payload(),
                "expected": {"survives": True},
            }
        ],
    )
    _write_suite(
        tmp_path,
        suite_id="gated",
        suite_tier="gated",
        cases=[
            {
                "case_id": "duplicate_case",
                "kind": "candidate_threshold",
                "decision_surface": "expected_absent",
                "risk_tags": ["false_positive_trap"],
                "anchor": True,
                "metric_key": "revenue",
                "candidate": _candidate_payload(),
                "expected": {"survives": False},
            }
        ],
    )

    with pytest.raises(ValueError, match="Duplicate calibration case id"):
        calibration.load_calibration_manifest(tmp_path)


def test_loader_rejects_unknown_risk_tags(tmp_path: Path) -> None:
    from src.analysis.extractor import calibration

    _write_suite(
        tmp_path,
        suite_id="fast",
        suite_tier="fast",
        cases=[
            {
                "case_id": "unknown_risk_tag_case",
                "kind": "candidate_threshold",
                "decision_surface": "threshold_boundary",
                "risk_tags": ["totally_unknown_tag"],
                "anchor": False,
                "metric_key": "revenue",
                "candidate": _candidate_payload(),
                "expected": {"survives": True},
            }
        ],
    )

    with pytest.raises(ValueError, match="Unknown risk tag"):
        calibration.load_calibration_manifest(tmp_path)


def test_loader_supports_multi_metric_parse_cases_and_source_strictness_tri_state(
    tmp_path: Path,
) -> None:
    from src.analysis.extractor import calibration

    _write_suite(
        tmp_path,
        suite_id="fast",
        suite_tier="fast",
        cases=[
            {
                "case_id": "multi_metric_case",
                "kind": "parse",
                "decision_surface": "winner_selection",
                "risk_tags": ["source_sensitive"],
                "anchor": False,
                "pipeline_mode": "tables+text",
                "tables": [
                    {
                        "flavor": "lattice",
                        "rows": [
                            ["Выручка", "5", "2 300 000"],
                            ["Чистая прибыль", "24", "100 000"],
                        ],
                    }
                ],
                "text": "",
                "expectations": {
                    "revenue": {
                        "survives": True,
                        "value": 2300000.0,
                        "expected_source": "table",
                        "source_strictness": "advisory",
                    },
                    "net_profit": {
                        "survives": True,
                        "value": 100000.0,
                        "source_strictness": "unspecified",
                    },
                },
            }
        ],
    )

    manifest = calibration.load_calibration_manifest(tmp_path)
    parse_case = manifest.parse_cases[0]

    assert tuple(sorted(parse_case.expectations)) == ("net_profit", "revenue")
    assert parse_case.expectations["revenue"].source_strictness == "advisory"
    assert parse_case.expectations["revenue"].expected_source == "table"
    assert parse_case.expectations["net_profit"].source_strictness == "unspecified"
    assert parse_case.expectations["net_profit"].expected_source is None


def test_fixture_ref_resolution_uses_minimal_contract(tmp_path: Path) -> None:
    from src.analysis.extractor import calibration

    fixture_root = tmp_path / "pdf_real_fixtures"
    fixture_root.mkdir()
    pdf_path = fixture_root / "fixture.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fixture")
    sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    manifest_path = fixture_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "id": "fixture-one",
                    "filename": "fixture.pdf",
                    "sha256": sha256,
                }
            ]
        ),
        encoding="utf-8",
    )

    resolved = calibration.resolve_fixture_ref(
        "fixture-one",
        fixture_manifest_path=manifest_path,
    )

    assert resolved.fixture_id == "fixture-one"
    assert resolved.path == pdf_path
    assert resolved.sha256 == sha256


def test_source_strictness_is_tri_state_and_advisory_mismatch_is_non_fatal(
    tmp_path: Path,
) -> None:
    from src.analysis.extractor import calibration
    from src.analysis.extractor.confidence_policy import RUNTIME_CONFIDENCE_POLICY

    _write_suite(
        tmp_path,
        suite_id="fast",
        suite_tier="fast",
        cases=[
            {
                "case_id": "advisory_source_case",
                "kind": "candidate_threshold",
                "decision_surface": "threshold_survival",
                "risk_tags": ["source_sensitive"],
                "anchor": False,
                "metric_key": "revenue",
                "candidate": _candidate_payload(source="text"),
                "expected": {
                    "survives": True,
                    "expected_source": "table",
                    "source_strictness": "advisory",
                },
            },
            {
                "case_id": "critical_source_case",
                "kind": "candidate_threshold",
                "decision_surface": "threshold_survival",
                "risk_tags": ["source_sensitive"],
                "anchor": False,
                "metric_key": "revenue",
                "candidate": _candidate_payload(source="text"),
                "expected": {
                    "survives": True,
                    "expected_source": "table",
                    "source_strictness": "critical",
                },
            },
        ],
    )

    manifest = calibration.load_calibration_manifest(tmp_path)
    runtime = calibration.EvaluationRuntime(
        name="runtime",
        confidence_policy=RUNTIME_CONFIDENCE_POLICY,
        threshold=manifest.threshold,
        strong_direct_threshold=RUNTIME_CONFIDENCE_POLICY.strong_direct_threshold,
    )
    report = calibration.evaluate_runtime(manifest, runtime)
    exported = calibration.report_to_dict(
        calibration.PolicyComparisonReport(
            manifest=manifest,
            baseline=report,
            candidate=report,
            shadow_policies={},
            case_diffs={},
            threshold_sweep={},
            invariant_checks=(),
            policy_diffs=(),
            suite_case_diffs={},
        )
    )

    assert report.case_outcomes["advisory_source_case"].correct is True
    assert report.case_outcomes["critical_source_case"].correct is False
    assert exported["candidate"]["source_mismatch_audit"]["advisory_mismatches"] == [
        "advisory_source_case"
    ]
    assert exported["candidate"]["source_mismatch_audit"]["critical_mismatches"] == [
        "critical_source_case"
    ]


def test_compare_policies_reports_per_suite_aggregate_and_stable_multi_metric_ids() -> (
    None
):
    from src.analysis.extractor import calibration
    from src.analysis.extractor.confidence_policy import (
        BASELINE_RUNTIME_CONFIDENCE_POLICY,
        RUNTIME_CONFIDENCE_POLICY,
    )

    manifest = calibration.load_calibration_manifest(_manifest_root(), suite="all")
    report = calibration.compare_policies(
        manifest,
        baseline_policy=BASELINE_RUNTIME_CONFIDENCE_POLICY,
        candidate_policy=RUNTIME_CONFIDENCE_POLICY,
        shadow_policies=calibration.DEFAULT_SHADOW_POLICIES,
    )
    exported = calibration.report_to_dict(report)

    assert set(exported["candidate"]["suites"]) == {"fast", "gated"}
    assert "aggregate" in exported["candidate"]
    assert "fast_inline_winner_pair::revenue" in exported["candidate"]["case_outcomes"]
    assert (
        "fast_inline_winner_pair::net_profit" in exported["candidate"]["case_outcomes"]
    )
    assert list(exported["candidate"]["case_outcomes"]) == sorted(
        exported["candidate"]["case_outcomes"]
    )
    assert exported["suite_case_diffs"]
    assert exported["threshold_sweep"]


def test_coverage_audit_tracks_required_surfaces_and_gated_anchors() -> None:
    from src.analysis.extractor import calibration
    from src.analysis.extractor.confidence_policy import (
        BASELINE_RUNTIME_CONFIDENCE_POLICY,
        RUNTIME_CONFIDENCE_POLICY,
    )

    manifest = calibration.load_calibration_manifest(_manifest_root(), suite="all")
    report = calibration.compare_policies(
        manifest,
        baseline_policy=BASELINE_RUNTIME_CONFIDENCE_POLICY,
        candidate_policy=RUNTIME_CONFIDENCE_POLICY,
    )
    exported = calibration.report_to_dict(report)
    audit = exported["coverage_audit"]

    assert audit["missing_required_surfaces"]["fast"] == []
    assert audit["missing_required_surfaces"]["all"] == []
    assert audit["underanchored_required_surfaces"]["gated"] == []
    assert audit["underanchored_required_surfaces"]["all"] == []
    assert audit["required_surfaces"] == [
        "threshold_boundary",
        "winner_selection",
        "merge_replacement",
        "expected_absent",
    ]
    assert audit["expansion_priority_surfaces"] == [
        "threshold_survival",
        "authoritative_override",
        "approximation_separation",
    ]


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

    manifest = calibration.load_calibration_manifest(_manifest_root(), suite="fast")
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


def test_threshold_sweep_keeps_survivor_count_monotonic() -> None:
    from src.analysis.extractor import calibration
    from src.analysis.extractor.confidence_policy import (
        BASELINE_RUNTIME_CONFIDENCE_POLICY,
        RUNTIME_CONFIDENCE_POLICY,
    )

    manifest = calibration.load_calibration_manifest(_manifest_root(), suite="fast")
    report = calibration.compare_policies(
        manifest,
        baseline_policy=BASELINE_RUNTIME_CONFIDENCE_POLICY,
        candidate_policy=RUNTIME_CONFIDENCE_POLICY,
    )

    for sweep_points in report.threshold_sweep.values():
        survivor_counts = [point.survivor_count for point in sweep_points]
        assert survivor_counts == sorted(survivor_counts, reverse=True)


def test_cli_parser_defaults_to_fast_suite() -> None:
    from scripts.run_extractor_confidence_calibration import _build_parser

    args = _build_parser().parse_args([])

    assert args.suite == "fast"
