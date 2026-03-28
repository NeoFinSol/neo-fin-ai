from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.maintenance.admin_cleanup import main


class TestAdminCleanupCli:
    def test_main_requires_target(self):
        with pytest.raises(SystemExit) as exc:
            main([])

        assert exc.value.code == 2

    def test_main_runs_analyses_dry_run_by_default(self, capsys):
        with patch(
            "src.maintenance.admin_cleanup.run_cleanup_job",
            new_callable=AsyncMock,
            return_value={
                "generated_at": "2026-03-28T12:00:00+00:00",
                "mode": "dry_run",
                "limit": 100,
                "targets": {"analyses": {"count": 1, "deleted": False, "task_ids": ["a"]}},
            },
        ) as mock_run:
            exit_code = main(["--analyses"])

        assert exit_code == 0
        kwargs = mock_run.await_args.kwargs
        assert kwargs["clean_analyses"] is True
        assert kwargs["clean_multi_sessions"] is False
        assert kwargs["execute"] is False
        captured = capsys.readouterr()
        assert '"mode": "dry_run"' in captured.out

    def test_main_runs_execute_for_selected_targets(self):
        with patch(
            "src.maintenance.admin_cleanup.run_cleanup_job",
            new_callable=AsyncMock,
            return_value={"generated_at": "2026-03-28T12:00:00+00:00", "mode": "execute", "limit": 50, "targets": {}},
        ) as mock_run:
            exit_code = main(
                [
                    "--analyses",
                    "--multi-sessions",
                    "--execute",
                    "--limit",
                    "50",
                    "--analysis-stale-hours",
                    "72",
                    "--multi-session-stale-hours",
                    "36",
                ]
            )

        assert exit_code == 0
        assert mock_run.await_args.kwargs == {
            "clean_analyses": True,
            "clean_multi_sessions": True,
            "execute": True,
            "limit": 50,
            "analysis_stale_hours": 72,
            "multi_session_stale_hours": 36,
        }
