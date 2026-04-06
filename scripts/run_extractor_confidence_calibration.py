from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.analysis.extractor import calibration
from src.analysis.extractor.confidence_policy import (
    BASELINE_RUNTIME_CONFIDENCE_POLICY,
    RUNTIME_CONFIDENCE_POLICY,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the internal extractor confidence calibration harness.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=calibration.DEFAULT_MANIFEST_PATH,
        help="Path to the suite-aware calibration manifest root or a single suite file.",
    )
    parser.add_argument(
        "--suite",
        choices=("fast", "gated", "all"),
        default="fast",
        help="Suite selector for the calibration harness.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format for the evidence pack.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the report to disk.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    manifest = calibration.load_calibration_manifest(args.manifest, suite=args.suite)
    report = calibration.compare_policies(
        manifest,
        baseline_policy=BASELINE_RUNTIME_CONFIDENCE_POLICY,
        candidate_policy=RUNTIME_CONFIDENCE_POLICY,
        shadow_policies=calibration.DEFAULT_SHADOW_POLICIES,
    )
    if args.format == "json":
        payload = json.dumps(
            calibration.report_to_dict(report),
            indent=2,
            ensure_ascii=False,
        )
    else:
        payload = calibration.render_calibration_report(report)

    if args.output is not None:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
