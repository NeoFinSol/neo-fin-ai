from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.core.runtime_events import broadcast_task_event
from src.db.crud import (
    mark_stale_analyses_failed,
    mark_stale_multi_sessions_failed,
)
from src.models.settings import app_settings


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _build_stale_cutoff(*, now: datetime, stale_minutes: int) -> datetime:
    return now - timedelta(minutes=stale_minutes)


async def _broadcast_recovered_analysis_failures(task_ids: list[str]) -> None:
    for task_id in task_ids:
        await broadcast_task_event(task_id, {
            "type": "status_update",
            "task_id": task_id,
            "status": "failed",
            "error": "Task runtime heartbeat expired",
            "reason_code": "runtime_stale_timeout",
        })


async def _broadcast_recovered_multi_session_failures(session_ids: list[str]) -> None:
    for session_id in session_ids:
        await broadcast_task_event(session_id, {
            "type": "status_update",
            "session_id": session_id,
            "status": "failed",
            "error": "Multi-analysis runtime heartbeat expired",
            "reason_code": "runtime_stale_timeout",
        })


async def run_runtime_recovery_job(
    *,
    recover_analyses: bool = False,
    recover_multi_sessions: bool = False,
    execute: bool = False,
    limit: int | None = None,
    analysis_stale_minutes: int | None = None,
    multi_session_stale_minutes: int | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """
    Find stale runtime rows and mark them failed in bounded batches.

    v1 intentionally does not requeue tasks automatically. Safe policy:
    stale runtime rows are marked failed with a diagnostic reason code.
    """
    if not recover_analyses and not recover_multi_sessions:
        raise ValueError("Select at least one recovery target")

    base_now = now or _utc_now()
    batch_limit = limit or app_settings.runtime_recovery_batch_limit
    analyses_minutes = analysis_stale_minutes or app_settings.analysis_runtime_stale_minutes
    multi_minutes = multi_session_stale_minutes or app_settings.multi_session_runtime_stale_minutes

    report: dict[str, object] = {
        "generated_at": base_now.isoformat(),
        "mode": "execute" if execute else "dry_run",
        "limit": batch_limit,
        "targets": {},
    }

    if recover_analyses:
        cutoff = _build_stale_cutoff(now=base_now, stale_minutes=analyses_minutes)
        result = await mark_stale_analyses_failed(
            stale_before=cutoff,
            limit=batch_limit,
            dry_run=not execute,
        )
        report["targets"]["analyses"] = {
            "stale_before": cutoff.isoformat(),
            "stale_minutes": analyses_minutes,
            **result,
        }
        if execute and result.get("updated"):
            await _broadcast_recovered_analysis_failures(result.get("task_ids", []))

    if recover_multi_sessions:
        cutoff = _build_stale_cutoff(now=base_now, stale_minutes=multi_minutes)
        result = await mark_stale_multi_sessions_failed(
            stale_before=cutoff,
            limit=batch_limit,
            dry_run=not execute,
        )
        report["targets"]["multi_sessions"] = {
            "stale_before": cutoff.isoformat(),
            "stale_minutes": multi_minutes,
            **result,
        }
        if execute and result.get("updated"):
            await _broadcast_recovered_multi_session_failures(result.get("session_ids", []))

    return report
