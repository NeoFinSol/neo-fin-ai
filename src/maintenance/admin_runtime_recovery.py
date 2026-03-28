from __future__ import annotations

import argparse
import asyncio
import json
import sys

from src.maintenance.runtime_recovery import run_runtime_recovery_job
from src.models.settings import app_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run NeoFin AI runtime recovery for stale in-progress rows."
    )
    parser.add_argument(
        "--analyses",
        action="store_true",
        help="Target stale single-analysis runtime rows.",
    )
    parser.add_argument(
        "--multi-sessions",
        action="store_true",
        help="Target stale multi-analysis runtime rows.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply recovery updates. Default mode is dry-run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=app_settings.runtime_recovery_batch_limit,
        help="Maximum rows per target to inspect/update in one run.",
    )
    parser.add_argument(
        "--analysis-stale-minutes",
        type=int,
        default=app_settings.analysis_runtime_stale_minutes,
        help="Runtime heartbeat timeout for analyses in minutes.",
    )
    parser.add_argument(
        "--multi-session-stale-minutes",
        type=int,
        default=app_settings.multi_session_runtime_stale_minutes,
        help="Runtime heartbeat timeout for multi-analysis sessions in minutes.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.analyses and not args.multi_sessions:
        parser.error("Select at least one target: --analyses and/or --multi-sessions")

    report = asyncio.run(
        run_runtime_recovery_job(
            recover_analyses=args.analyses,
            recover_multi_sessions=args.multi_sessions,
            execute=args.execute,
            limit=args.limit,
            analysis_stale_minutes=args.analysis_stale_minutes,
            multi_session_stale_minutes=args.multi_session_stale_minutes,
        )
    )
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
