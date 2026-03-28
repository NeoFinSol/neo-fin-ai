from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.db.crud import cleanup_analyses, cleanup_multi_sessions
from src.models.settings import app_settings


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _build_stale_cutoff(*, now: datetime, stale_hours: int) -> datetime:
    return now - timedelta(hours=stale_hours)


async def run_cleanup_job(
    *,
    clean_analyses: bool = False,
    clean_multi_sessions: bool = False,
    execute: bool = False,
    limit: int | None = None,
    analysis_stale_hours: int | None = None,
    multi_session_stale_hours: int | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """
    Run a bounded maintenance cleanup job.

    v1 intentionally cleans only stale in-progress rows. Terminal business history
    is not deleted by default.
    """
    if not clean_analyses and not clean_multi_sessions:
        raise ValueError("Select at least one cleanup target")

    base_now = now or _utc_now()
    batch_limit = limit or app_settings.cleanup_batch_limit
    analyses_hours = analysis_stale_hours or app_settings.analysis_cleanup_stale_hours
    multi_hours = multi_session_stale_hours or app_settings.multi_session_stale_hours

    report: dict[str, object] = {
        "generated_at": base_now.isoformat(),
        "mode": "execute" if execute else "dry_run",
        "limit": batch_limit,
        "targets": {},
    }

    if clean_analyses:
        cutoff = _build_stale_cutoff(now=base_now, stale_hours=analyses_hours)
        result = await cleanup_analyses(
            stale_processing_before=cutoff,
            limit=batch_limit,
            dry_run=not execute,
        )
        report["targets"]["analyses"] = {
            "stale_processing_before": cutoff.isoformat(),
            "stale_hours": analyses_hours,
            **result,
        }

    if clean_multi_sessions:
        cutoff = _build_stale_cutoff(now=base_now, stale_hours=multi_hours)
        result = await cleanup_multi_sessions(
            stale_processing_before=cutoff,
            limit=batch_limit,
            dry_run=not execute,
        )
        report["targets"]["multi_sessions"] = {
            "stale_processing_before": cutoff.isoformat(),
            "stale_hours": multi_hours,
            **result,
        }

    return report
