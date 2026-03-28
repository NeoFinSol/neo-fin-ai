from __future__ import annotations

import argparse
import asyncio
import json
import sys

from src.maintenance.cleanup_jobs import run_cleanup_job
from src.models.settings import app_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run bounded NeoFin AI cleanup jobs for stale in-progress rows."
    )
    parser.add_argument(
        "--analyses",
        action="store_true",
        help="Target stale analyses with status uploading/processing only.",
    )
    parser.add_argument(
        "--multi-sessions",
        action="store_true",
        help="Target stale multi-analysis sessions with status processing only.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply deletions. Default mode is dry-run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=app_settings.cleanup_batch_limit,
        help="Maximum rows per target to inspect/delete in one run.",
    )
    parser.add_argument(
        "--analysis-stale-hours",
        type=int,
        default=app_settings.analysis_cleanup_stale_hours,
        help="Staleness threshold for analyses in hours.",
    )
    parser.add_argument(
        "--multi-session-stale-hours",
        type=int,
        default=app_settings.multi_session_stale_hours,
        help="Staleness threshold for multi-analysis sessions in hours.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.analyses and not args.multi_sessions:
        parser.error("Select at least one target: --analyses and/or --multi-sessions")

    report = asyncio.run(
        run_cleanup_job(
            clean_analyses=args.analyses,
            clean_multi_sessions=args.multi_sessions,
            execute=args.execute,
            limit=args.limit,
            analysis_stale_hours=args.analysis_stale_hours,
            multi_session_stale_hours=args.multi_session_stale_hours,
        )
    )
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
