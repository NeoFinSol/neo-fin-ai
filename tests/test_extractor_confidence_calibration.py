from __future__ import annotations

import hashlib
import json
import logging
import sys
import warnings
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


def _write_fixture_manifest(root: Path, *, fixture_id: str = "fixture-one") -> Path:
    fixture_root = root / "pdf_real_fixtures"
    fixture_root.mkdir()
    pdf_path = fixture_root / "fixture.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fixture")
    sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    manifest_path = fixture_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "id": fixture_id,
                    "filename": "fixture.pdf",
                    "sha256": sha256,
                }
            ]
        ),
        encoding="utf-8",
    )
    return manifest_path


def _write_compare_demo_suites(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _write_suite(
        root,
        suite_id="fast",
        suite_tier="fast",
        cases=[
            {
                "case_id": "fast_boundary_text_code",
                "kind": "candidate_threshold",
                "decision_surface": "threshold_boundary",
                "risk_tags": ["boundary_near_0_5", "source_sensitive"],
                "anchor": False,
                "metric_key": "revenue",
                "candidate": _candidate_payload(
                    value=2400000.0,
                    source="text",
                    match_semantics="code_match",
                    candidate_quality=95,
                ),
                "expected": {
                    "survives": True,
                    "expected_source": "text",
                    "source_strictness": "critical",
                },
            },
            {
                "case_id": "fast_inline_winner_pair",
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
                        "source_strictness": "critical",
                    },
                    "net_profit": {
                        "survives": True,
                        "value": 100000.0,
                        "expected_source": "table",
                        "source_strictness": "advisory",
                    },
                },
            },
            {
                "case_id": "fast_llm_replacement",
                "kind": "merge",
                "decision_surface": "merge_replacement",
                "risk_tags": ["replacement_path"],
                "anchor": False,
                "metric_key": "revenue",
                "fallback_candidate": _candidate_payload(
                    value=1200000.0,
                    source="text",
                    match_semantics="keyword_match",
                    candidate_quality=50,
                ),
                "llm_metadata": {
                    "value": 15000000.0,
                    "confidence": 0.92,
                    "source": "text",
                    "evidence_version": "v2",
                    "match_semantics": "keyword_match",
                    "inference_mode": "direct",
                    "postprocess_state": "none",
                    "reason_code": "llm_extraction",
                    "signal_flags": [],
                    "candidate_quality": None,
                    "authoritative_override": False,
                },
                "expected": {
                    "winner": "llm",
                },
            },
            {
                "case_id": "fast_expected_absent_case",
                "kind": "candidate_threshold",
                "decision_surface": "expected_absent",
                "risk_tags": ["false_positive_trap", "low_confidence", "weak_keyword"],
                "anchor": False,
                "metric_key": "revenue",
                "candidate": _candidate_payload(
                    value=1200000.0,
                    source="text",
                    match_semantics="keyword_match",
                    candidate_quality=50,
                ),
                "expected": {"survives": False},
            },
        ],
    )
    _write_suite(
        root,
        suite_id="gated",
        suite_tier="gated",
        cases=[
            {
                "case_id": "gated_boundary_anchor",
                "kind": "candidate_threshold",
                "decision_surface": "threshold_boundary",
                "risk_tags": ["boundary_near_0_5"],
                "anchor": True,
                "fixture_ref": "fixture-anchor",
                "metric_key": "revenue",
                "candidate": _candidate_payload(
                    value=2400000.0,
                    source="text",
                    match_semantics="code_match",
                    candidate_quality=95,
                ),
                "expected": {"survives": True},
            },
            {
                "case_id": "gated_winner_anchor",
                "kind": "candidate_threshold",
                "decision_surface": "winner_selection",
                "risk_tags": ["source_sensitive"],
                "anchor": True,
                "fixture_ref": "fixture-anchor",
                "metric_key": "current_assets",
                "candidate": _candidate_payload(
                    value=243770000.0,
                    source="text",
                    match_semantics="code_match",
                    candidate_quality=95,
                ),
                "expected": {"survives": True},
            },
            {
                "case_id": "gated_merge_anchor",
                "kind": "merge",
                "decision_surface": "merge_replacement",
                "risk_tags": ["replacement_path"],
                "anchor": True,
                "fixture_ref": "fixture-anchor",
                "metric_key": "revenue",
                "fallback_candidate": _candidate_payload(
                    value=1200000.0,
                    source="text",
                    match_semantics="keyword_match",
                    candidate_quality=50,
                ),
                "llm_metadata": {
                    "value": 15000000.0,
                    "confidence": 0.92,
                    "source": "text",
                    "evidence_version": "v2",
                    "match_semantics": "keyword_match",
                    "inference_mode": "direct",
                    "postprocess_state": "none",
                    "reason_code": "llm_extraction",
                    "signal_flags": [],
                    "candidate_quality": None,
                    "authoritative_override": False,
                },
                "expected": {
                    "winner": "llm",
                },
            },
            {
                "case_id": "gated_expected_absent_anchor",
                "kind": "candidate_threshold",
                "decision_surface": "expected_absent",
                "risk_tags": [
                    "false_positive_trap",
                    "low_confidence",
                    "weak_ocr_direct",
                ],
                "anchor": True,
                "fixture_ref": "fixture-anchor",
                "metric_key": "total_assets",
                "candidate": _candidate_payload(
                    value=2759767000.0,
                    source="ocr",
                    match_semantics="exact",
                    candidate_quality=50,
                    is_exact=True,
                ),
                "expected": {"survives": False},
            },
        ],
    )
    return root


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


def test_fixture_ref_resolution_rejects_paths_outside_manifest_root(
    tmp_path: Path,
) -> None:
    from src.analysis.extractor import calibration

    fixture_root = tmp_path / "pdf_real_fixtures"
    fixture_root.mkdir()
    escaped_pdf = tmp_path / "outside.pdf"
    escaped_pdf.write_bytes(b"%PDF-1.4 escaped-fixture")
    sha256 = hashlib.sha256(escaped_pdf.read_bytes()).hexdigest()
    manifest_path = fixture_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "id": "fixture-one",
                    "filename": "..\\outside.pdf",
                    "sha256": sha256,
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="committed fixture manifest root"):
        calibration.resolve_fixture_ref(
            "fixture-one",
            fixture_manifest_path=manifest_path,
        )


def test_loader_accepts_force_ocr_pipeline_mode(tmp_path: Path) -> None:
    from src.analysis.extractor import calibration

    _write_suite(
        tmp_path,
        suite_id="gated",
        suite_tier="gated",
        cases=[
            {
                "case_id": "force_ocr_case",
                "kind": "parse",
                "decision_surface": "threshold_boundary",
                "risk_tags": ["ocr_fragile", "boundary_near_0_5"],
                "anchor": True,
                "fixture_ref": "fixture-one",
                "pipeline_mode": "force_ocr",
                "expectations": {
                    "accounts_receivable": {
                        "survives": True,
                        "value": 26998240000.0,
                    }
                },
            }
        ],
    )

    manifest = calibration.load_calibration_manifest(tmp_path)

    assert manifest.parse_cases[0].pipeline_mode == "force_ocr"


def test_force_ocr_uses_ocr_text_and_never_extracts_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.analysis.extractor import calibration

    fixture_root = tmp_path / "pdf_real_fixtures"
    fixture_root.mkdir()
    pdf_path = fixture_root / "fixture.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 force-ocr-fixture")
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

    calls: list[str] = []

    def _extract_text(_: str) -> str:
        calls.append("extract_text")
        raise AssertionError("force_ocr must not call extract_text")

    def _extract_text_from_scanned(_: str) -> str:
        calls.append("extract_text_from_scanned")
        return "ocr text"

    def _extract_tables(_: str) -> list[dict]:
        calls.append("extract_tables")
        raise AssertionError("force_ocr must not call extract_tables")

    monkeypatch.setattr("src.analysis.pdf_extractor.extract_text", _extract_text)
    monkeypatch.setattr(
        "src.analysis.pdf_extractor.extract_text_from_scanned",
        _extract_text_from_scanned,
    )
    monkeypatch.setattr("src.analysis.pdf_extractor.extract_tables", _extract_tables)

    calibration._load_fixture_parse_inputs.cache_clear()
    try:
        tables, text = calibration._load_fixture_parse_inputs(
            str(manifest_path.resolve()),
            "fixture-one",
            "force_ocr",
        )
    finally:
        calibration._load_fixture_parse_inputs.cache_clear()

    assert tables == []
    assert text == "ocr text"
    assert calls == ["extract_text_from_scanned"]


def test_expected_scanned_does_not_constrain_pipeline_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.analysis.extractor import calibration

    fixture_root = tmp_path / "pdf_real_fixtures"
    fixture_root.mkdir()
    pdf_path = fixture_root / "fixture.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 text-only-fixture")
    sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    manifest_path = fixture_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "id": "fixture-one",
                    "filename": "fixture.pdf",
                    "sha256": sha256,
                    "expected_scanned": True,
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "src.analysis.pdf_extractor.extract_text", lambda _: "plain text"
    )
    monkeypatch.setattr(
        "src.analysis.pdf_extractor.extract_text_from_scanned",
        lambda _: (_ for _ in ()).throw(
            AssertionError("text_only should not use OCR path")
        ),
    )

    calibration._load_fixture_parse_inputs.cache_clear()
    try:
        tables, text = calibration._load_fixture_parse_inputs(
            str(manifest_path.resolve()),
            "fixture-one",
            "text_only",
        )
    finally:
        calibration._load_fixture_parse_inputs.cache_clear()

    assert tables == []
    assert text == "plain text"


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


def test_authoritative_override_merge_expectations_fail_on_source_or_reason_drift(
    tmp_path: Path,
) -> None:
    from src.analysis.extractor import calibration
    from src.analysis.extractor.confidence_policy import RUNTIME_CONFIDENCE_POLICY

    _write_suite(
        tmp_path,
        suite_id="gated",
        suite_tier="gated",
        cases=[
            {
                "case_id": "override_contract_case",
                "kind": "merge",
                "decision_surface": "authoritative_override",
                "risk_tags": ["replacement_path", "source_sensitive"],
                "anchor": True,
                "metric_key": "ebitda",
                "fallback_metadata": {
                    "value": 85628000000.0,
                    "confidence": 0.95,
                    "source": "issuer_fallback",
                    "evidence_version": "v2",
                    "match_semantics": "not_applicable",
                    "inference_mode": "policy_override",
                    "postprocess_state": "none",
                    "reason_code": "issuer_repo_override",
                    "signal_flags": [],
                    "candidate_quality": None,
                    "authoritative_override": True,
                },
                "llm_metadata": {
                    "value": 81000000000.0,
                    "confidence": 0.99,
                    "source": "text",
                    "evidence_version": "v2",
                    "match_semantics": "keyword_match",
                    "inference_mode": "direct",
                    "postprocess_state": "none",
                    "reason_code": "llm_extraction",
                    "signal_flags": [],
                    "candidate_quality": None,
                    "authoritative_override": False,
                },
                "expected": {
                    "winner": "fallback",
                    "expected_source": "issuer_fallback",
                    "expected_authoritative_override": True,
                    "expected_reason_code": "issuer_repo_override_v2",
                },
            }
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

    assert report.case_outcomes["override_contract_case"].correct is False


def test_compare_policies_reports_per_suite_aggregate_and_stable_multi_metric_ids(
    tmp_path: Path,
) -> None:
    from src.analysis.extractor import calibration
    from src.analysis.extractor.confidence_policy import (
        BASELINE_RUNTIME_CONFIDENCE_POLICY,
        RUNTIME_CONFIDENCE_POLICY,
    )

    temp_root = _write_compare_demo_suites(tmp_path)
    manifest = calibration.load_calibration_manifest(temp_root, suite="all")
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


def test_coverage_audit_tracks_required_surfaces_and_gated_anchors(
    tmp_path: Path,
) -> None:
    from src.analysis.extractor import calibration
    from src.analysis.extractor.confidence_policy import (
        BASELINE_RUNTIME_CONFIDENCE_POLICY,
        RUNTIME_CONFIDENCE_POLICY,
    )

    temp_root = _write_compare_demo_suites(tmp_path)
    manifest = calibration.load_calibration_manifest(temp_root, suite="all")
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


def test_evaluate_runtime_captures_fixture_diagnostics_in_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.analysis.extractor import calibration
    from src.analysis.extractor.confidence_policy import RUNTIME_CONFIDENCE_POLICY

    fixture_manifest_path = _write_fixture_manifest(tmp_path)
    _write_suite(
        tmp_path,
        suite_id="gated",
        suite_tier="gated",
        cases=[
            {
                "case_id": "diagnostic_fixture_case",
                "kind": "parse",
                "decision_surface": "threshold_boundary",
                "risk_tags": ["boundary_near_0_5", "ocr_fragile"],
                "anchor": True,
                "fixture_ref": "fixture-one",
                "pipeline_mode": "tables+text",
                "expectations": {
                    "revenue": {
                        "survives": True,
                        "value": 2300000.0,
                        "expected_source": "table",
                        "source_strictness": "critical",
                    }
                },
            }
        ],
    )

    monkeypatch.setattr("src.analysis.pdf_extractor.extract_text", lambda _: "")

    def _extract_tables(_: str) -> list[dict[str, object]]:
        warnings.warn("No tables found in table area 1", UserWarning)
        logging.getLogger("src.analysis.extractor.legacy_helpers").warning(
            "Camelot timed out after 45s (flavor=stream), skipping"
        )
        logging.getLogger("src.analysis.extractor.legacy_helpers").warning(
            "OCR extraction failed: fallback failed"
        )
        return [
            {
                "flavor": "stream",
                "rows": [["Выручка", "5", "2 300 000"]],
            }
        ]

    monkeypatch.setattr("src.analysis.pdf_extractor.extract_tables", _extract_tables)

    manifest = calibration.load_calibration_manifest(tmp_path, suite="gated")
    runtime = calibration.EvaluationRuntime(
        name="runtime",
        confidence_policy=RUNTIME_CONFIDENCE_POLICY,
        threshold=manifest.threshold,
        strong_direct_threshold=RUNTIME_CONFIDENCE_POLICY.strong_direct_threshold,
    )

    report = calibration.evaluate_runtime(
        manifest,
        runtime,
        fixture_manifest_path=fixture_manifest_path,
    )

    assert [event.kind for event in report.diagnostics] == [
        "camelot_warning",
        "camelot_timeout",
        "ocr_fallback_warning",
    ]
    assert [event.message for event in report.diagnostics] == [
        "No tables found in table area 1",
        "Camelot timed out after 45s (flavor=stream), skipping",
        "OCR extraction failed: fallback failed",
    ]

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
            coverage_audit=None,
        )
    )
    candidate_diagnostics = exported["candidate"]["diagnostics"]
    case_events = candidate_diagnostics["cases"]["diagnostic_fixture_case"]

    assert [event["kind"] for event in case_events] == [
        "camelot_warning",
        "camelot_timeout",
        "ocr_fallback_warning",
    ]
    assert candidate_diagnostics["aggregate"]["counts"] == {
        "camelot_warning": 1,
        "camelot_timeout": 1,
        "ocr_fallback_warning": 1,
        "unexpected_error": 0,
    }


def test_cli_main_keeps_calibration_output_quiet_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts.run_extractor_confidence_calibration import main
    from src.analysis.extractor import calibration as calibration_module

    fixture_manifest_path = _write_fixture_manifest(tmp_path)
    original_compare_policies = calibration_module.compare_policies
    _write_suite(
        tmp_path,
        suite_id="fast",
        suite_tier="fast",
        cases=[
            {
                "case_id": "quiet_cli_case",
                "kind": "parse",
                "decision_surface": "threshold_boundary",
                "risk_tags": ["boundary_near_0_5"],
                "anchor": False,
                "fixture_ref": "fixture-one",
                "pipeline_mode": "tables+text",
                "expectations": {
                    "revenue": {
                        "survives": True,
                        "value": 2300000.0,
                    }
                },
            }
        ],
    )

    monkeypatch.setattr("src.analysis.pdf_extractor.extract_text", lambda _: "")

    def _extract_tables(_: str) -> list[dict[str, object]]:
        warnings.warn("No tables found in table area 1", UserWarning)
        logging.getLogger("src.analysis.extractor.legacy_helpers").warning(
            "Camelot timed out after 45s (flavor=stream), skipping"
        )
        return [
            {
                "flavor": "stream",
                "rows": [["Выручка", "5", "2 300 000"]],
            }
        ]

    monkeypatch.setattr("src.analysis.pdf_extractor.extract_tables", _extract_tables)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_extractor_confidence_calibration.py",
            "--manifest",
            str(tmp_path),
            "--suite",
            "fast",
            "--format",
            "json",
        ],
    )
    monkeypatch.setattr(
        "scripts.run_extractor_confidence_calibration.calibration.compare_policies",
        lambda manifest, **kwargs: original_compare_policies(
            manifest,
            fixture_manifest_path=fixture_manifest_path,
            **kwargs,
        ),
    )

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert (
        payload["candidate"]["diagnostics"]["aggregate"]["counts"]["camelot_warning"]
        >= 1
    )
    assert (
        payload["candidate"]["diagnostics"]["aggregate"]["counts"]["camelot_timeout"]
        >= 1
    )


def test_evaluate_runtime_preserves_failure_on_unexpected_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.analysis.extractor import calibration
    from src.analysis.extractor.confidence_policy import RUNTIME_CONFIDENCE_POLICY

    fixture_manifest_path = _write_fixture_manifest(tmp_path)
    _write_suite(
        tmp_path,
        suite_id="gated",
        suite_tier="gated",
        cases=[
            {
                "case_id": "unexpected_failure_case",
                "kind": "parse",
                "decision_surface": "threshold_boundary",
                "risk_tags": ["low_confidence"],
                "anchor": False,
                "fixture_ref": "fixture-one",
                "pipeline_mode": "tables+text",
                "expectations": {
                    "revenue": {
                        "survives": True,
                    }
                },
            }
        ],
    )

    monkeypatch.setattr("src.analysis.pdf_extractor.extract_text", lambda _: "")
    monkeypatch.setattr(
        "src.analysis.pdf_extractor.extract_tables",
        lambda _: (_ for _ in ()).throw(RuntimeError("unexpected boom")),
    )

    manifest = calibration.load_calibration_manifest(tmp_path, suite="gated")
    runtime = calibration.EvaluationRuntime(
        name="runtime",
        confidence_policy=RUNTIME_CONFIDENCE_POLICY,
        threshold=manifest.threshold,
        strong_direct_threshold=RUNTIME_CONFIDENCE_POLICY.strong_direct_threshold,
    )

    with pytest.raises(RuntimeError, match="unexpected boom"):
        calibration.evaluate_runtime(
            manifest,
            runtime,
            fixture_manifest_path=fixture_manifest_path,
        )
