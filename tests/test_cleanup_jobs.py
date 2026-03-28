from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.maintenance.cleanup_jobs import run_cleanup_job


class TestRunCleanupJob:
    @pytest.mark.asyncio
    async def test_requires_at_least_one_target(self):
        with pytest.raises(ValueError):
            await run_cleanup_job()

    @pytest.mark.asyncio
    async def test_analyses_dry_run_uses_stale_processing_only(self):
        now = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
        with patch(
            "src.maintenance.cleanup_jobs.cleanup_analyses",
            new_callable=AsyncMock,
            return_value={"count": 2, "task_ids": ["a", "b"], "deleted": False},
        ) as mock_cleanup:
            report = await run_cleanup_job(
                clean_analyses=True,
                analysis_stale_hours=48,
                limit=25,
                now=now,
            )

        kwargs = mock_cleanup.await_args.kwargs
        assert "terminal_before" not in kwargs
        assert kwargs["stale_processing_before"] == now - timedelta(hours=48)
        assert kwargs["limit"] == 25
        assert kwargs["dry_run"] is True
        assert report["mode"] == "dry_run"
        assert report["targets"]["analyses"]["count"] == 2

    @pytest.mark.asyncio
    async def test_multi_sessions_execute_uses_stale_processing_only(self):
        now = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
        with patch(
            "src.maintenance.cleanup_jobs.cleanup_multi_sessions",
            new_callable=AsyncMock,
            return_value={"count": 1, "session_ids": ["s1"], "deleted": True},
        ) as mock_cleanup:
            report = await run_cleanup_job(
                clean_multi_sessions=True,
                execute=True,
                multi_session_stale_hours=24,
                limit=10,
                now=now,
            )

        kwargs = mock_cleanup.await_args.kwargs
        assert "terminal_before" not in kwargs
        assert kwargs["stale_processing_before"] == now - timedelta(hours=24)
        assert kwargs["limit"] == 10
        assert kwargs["dry_run"] is False
        assert report["mode"] == "execute"
        assert report["targets"]["multi_sessions"]["deleted"] is True
