"""Tests for database CRUD operations."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.db.crud import (
    cleanup_analyses,
    cleanup_multi_sessions,
    create_analysis,
    create_multi_session,
    find_analysis_cleanup_candidates,
    find_multi_session_cleanup_candidates,
    find_stale_analysis_runtime_candidates,
    find_stale_multi_session_runtime_candidates,
    get_analysis,
    get_multi_session,
    is_analysis_cancel_requested,
    is_multi_session_cancel_requested,
    mark_analysis_cancelled,
    mark_multi_session_cancelled,
    mark_stale_analyses_failed,
    mark_stale_multi_sessions_failed,
    request_analysis_cancel,
    request_multi_session_cancel,
    touch_analysis_runtime_heartbeat,
    touch_multi_session_runtime_heartbeat,
    update_analysis,
)


class TestCreateAnalysis:
    """Tests for create_analysis function."""

    @pytest.mark.asyncio
    async def test_successful_creation(self):
        """Test successful analysis creation."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_analysis = MagicMock()
        mock_analysis.task_id = "test-123"
        mock_analysis.status = "pending"
        mock_analysis.result = None
        
        # Setup session to return our mock analysis after add
        def add_side_effect(obj):
            obj.id = 1  # Simulate auto-generated ID
            
        mock_session.add.side_effect = add_side_effect
        
        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager
        
        with patch('src.db.crud.get_session_maker', return_value=mock_session_maker):
            result = await create_analysis("test-123", "pending", None)
            
            assert result is not None
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_creation_with_result(self):
        """Test creating analysis with result data."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_analysis = MagicMock()
        result_data = {
            "filename": "report.pdf",
            "data": {
                "scanned": False,
                "score": {"score": 85.5, "risk_level": "low", "confidence_score": 0.9},
                "metrics": {"revenue": 100},
            },
        }
        
        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager
        
        with patch('src.db.crud.get_session_maker', return_value=mock_session_maker):
            await create_analysis("test-456", "completed", result_data)
            
            # Verify analysis was created with correct parameters
            call_args = mock_session.add.call_args
            analysis_obj = call_args[0][0]
            assert analysis_obj.status == "completed"
            assert analysis_obj.result == result_data
            assert analysis_obj.score == 85.5
            assert analysis_obj.filename == "report.pdf"

    @pytest.mark.asyncio
    async def test_sqlalchemy_error_handling(self):
        """Test SQLAlchemyError handling."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock(side_effect=SQLAlchemyError("Database connection failed"))
        mock_session.rollback = AsyncMock()
        
        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager
        
        with patch('src.db.crud.get_session_maker', return_value=mock_session_maker):
            with pytest.raises(SQLAlchemyError):
                await create_analysis("test-789", "pending", None)
            
            # Verify rollback was called
            mock_session.rollback.assert_called_once()


class TestUpdateAnalysis:
    """Tests for update_analysis function."""

    @pytest.mark.asyncio
    async def test_successful_update(self):
        """Test successful analysis update."""
        mock_existing = MagicMock()
        mock_existing.task_id = "test-123"
        mock_existing.status = "pending"
        mock_existing.result = None
        
        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=mock_existing)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager
        
        with patch('src.db.crud.get_session_maker', return_value=mock_session_maker):
            result = await update_analysis("test-123", "completed", {"data": "result"})
            
            assert result is not None
            assert result.status == "completed"
            assert result.result == {"data": "result"}
            assert result.score is None
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_derives_summary_columns_from_result(self):
        """Summary columns should be dual-written from the same JSON snapshot."""
        mock_existing = MagicMock()
        mock_existing.task_id = "test-123"
        mock_existing.status = "processing"
        mock_existing.result = None

        payload = {
            "filename": "report.pdf",
            "data": {
                "scanned": True,
                "score": {
                    "score": 72.5,
                    "risk_level": "medium",
                    "confidence_score": 0.8,
                },
            },
        }

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=mock_existing)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch('src.db.crud.get_session_maker', return_value=mock_session_maker):
            result = await update_analysis("test-123", "completed", payload)

            assert result.filename == "report.pdf"
            assert result.score == 72.5
            assert result.risk_level == "medium"
            assert result.scanned is True
            assert result.confidence_score == 0.8
            assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_update_failure_payload_sets_error_message(self):
        """Failed rows should preserve error_message as typed summary data."""
        mock_existing = MagicMock()
        mock_existing.task_id = "test-123"
        mock_existing.status = "processing"
        mock_existing.result = None

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=mock_existing)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch('src.db.crud.get_session_maker', return_value=mock_session_maker):
            result = await update_analysis("test-123", "failed", {"error": "boom"})

            assert result.error_message == "boom"
            assert result.completed_at is None

    @pytest.mark.asyncio
    async def test_update_without_result_preserves_existing_snapshot(self):
        """Status-only updates should not erase previously stored result/summary."""
        existing_payload = {
            "filename": "report.pdf",
            "data": {
                "scanned": False,
                "score": {
                    "score": 66.0,
                    "risk_level": "high",
                    "confidence_score": 0.7,
                },
            },
        }
        mock_existing = MagicMock()
        mock_existing.task_id = "test-123"
        mock_existing.status = "processing"
        mock_existing.result = existing_payload

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=mock_existing)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch('src.db.crud.get_session_maker', return_value=mock_session_maker):
            result = await update_analysis("test-123", "failed", None)

            assert result.result == existing_payload
            assert result.filename == "report.pdf"
            assert result.score == 66.0
            assert result.risk_level == "high"
            assert result.scanned is False
            assert result.confidence_score == 0.7
            assert result.completed_at is None

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_none(self):
        """Test updating nonexistent analysis returns None."""
        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=None)
        
        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager
        
        with patch('src.db.crud.get_session_maker', return_value=mock_session_maker):
            result = await update_analysis("nonexistent-id", "completed", None)
            
            assert result is None
            mock_session.scalar.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_only_status(self):
        """Test status-only update preserves the existing snapshot."""
        mock_existing = MagicMock()
        mock_existing.task_id = "test-123"
        mock_existing.status = "processing"
        mock_existing.result = {"partial": "data"}
        
        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=mock_existing)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager
        
        with patch('src.db.crud.get_session_maker', return_value=mock_session_maker):
            await update_analysis("test-123", "failed", None)
            
            assert mock_existing.status == "failed"
            assert mock_existing.result == {"partial": "data"}

    @pytest.mark.asyncio
    async def test_request_analysis_cancel_sets_timestamp(self):
        mock_existing = MagicMock()
        mock_existing.task_id = "test-123"
        mock_existing.status = "processing"
        mock_existing.cancel_requested_at = None

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=mock_existing)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch("src.db.crud.get_session_maker", return_value=mock_session_maker):
            result = await request_analysis_cancel("test-123")

        assert result.cancel_requested_at is not None
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_analysis_cancelled_sets_runtime_fields(self):
        mock_existing = MagicMock()
        mock_existing.task_id = "test-123"
        mock_existing.status = "processing"
        mock_existing.result = None
        mock_existing.cancel_requested_at = None
        mock_existing.cancelled_at = None
        mock_existing.runtime_heartbeat_at = None

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=mock_existing)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        payload = {"error": "Task cancelled by user", "reason_code": "cancelled_by_request"}

        with patch("src.db.crud.get_session_maker", return_value=mock_session_maker):
            result = await mark_analysis_cancelled("test-123", payload)

        assert result.status == "cancelled"
        assert result.cancel_requested_at is not None
        assert result.cancelled_at is not None
        assert result.runtime_heartbeat_at is not None

    @pytest.mark.asyncio
    async def test_is_analysis_cancel_requested_uses_db_state(self):
        mock_existing = MagicMock()
        mock_existing.status = "processing"
        mock_existing.cancel_requested_at = datetime.now(timezone.utc)

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=mock_existing)

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch("src.db.crud.get_session_maker", return_value=mock_session_maker):
            assert await is_analysis_cancel_requested("test-123") is True

    @pytest.mark.asyncio
    async def test_touch_analysis_runtime_heartbeat_updates_timestamp(self):
        mock_existing = MagicMock()
        mock_existing.status = "processing"
        mock_existing.runtime_heartbeat_at = None

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=mock_existing)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch("src.db.crud.get_session_maker", return_value=mock_session_maker):
            result = await touch_analysis_runtime_heartbeat("test-123")

        assert result.runtime_heartbeat_at is not None

    @pytest.mark.asyncio
    async def test_update_sqlalchemy_error(self):
        """Test SQLAlchemyError during update."""
        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(side_effect=SQLAlchemyError("Query failed"))
        mock_session.rollback = AsyncMock()
        
        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager
        
        with patch('src.db.crud.get_session_maker', return_value=mock_session_maker):
            with pytest.raises(SQLAlchemyError):
                await update_analysis("test-123", "completed", None)
            
            mock_session.rollback.assert_called_once()


class TestGetAnalysis:
    """Tests for get_analysis function."""

    @pytest.mark.asyncio
    async def test_successful_get(self):
        """Test successfully retrieving analysis."""
        mock_analysis = MagicMock()
        mock_analysis.task_id = "test-123"
        mock_analysis.status = "completed"
        
        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=mock_analysis)
        
        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager
        
        with patch('src.db.crud.get_session_maker', return_value=mock_session_maker):
            result = await get_analysis("test-123")
            
            assert result is not None
            assert result.task_id == "test-123"
            assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self):
        """Test getting nonexistent analysis returns None."""
        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=None)
        
        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager
        
        with patch('src.db.crud.get_session_maker', return_value=mock_session_maker):
            result = await get_analysis("nonexistent-id")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_get_sqlalchemy_error_raises(self):
        """DB read errors should bubble up instead of masquerading as missing rows."""
        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(side_effect=SQLAlchemyError("Connection error"))
        
        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager
        
        with patch('src.db.crud.get_session_maker', return_value=mock_session_maker):
            with pytest.raises(SQLAlchemyError):
                await get_analysis("test-123")


class TestMultiSessionCrud:
    """Tests for multi-session CRUD helpers."""

    @pytest.mark.asyncio
    async def test_create_multi_session_defaults_to_processing(self):
        """New sessions should start with processing status and zeroed progress."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch("src.db.crud.get_session_maker", return_value=mock_session_maker):
            await create_multi_session("session-123")

        created_obj = mock_session.add.call_args[0][0]
        assert created_obj.status == "processing"
        assert created_obj.progress == {"completed": 0, "total": 0}

    @pytest.mark.asyncio
    async def test_get_multi_session_sqlalchemy_error_raises(self):
        """Session lookup must not hide DB failures behind 404 behaviour."""
        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(side_effect=SQLAlchemyError("Connection error"))

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch("src.db.crud.get_session_maker", return_value=mock_session_maker):
            with pytest.raises(SQLAlchemyError):
                await get_multi_session("session-123")

    @pytest.mark.asyncio
    async def test_request_multi_session_cancel_sets_timestamp(self):
        mock_record = MagicMock()
        mock_record.session_id = "session-123"
        mock_record.status = "processing"
        mock_record.cancel_requested_at = None

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=mock_record)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch("src.db.crud.get_session_maker", return_value=mock_session_maker):
            result = await request_multi_session_cancel("session-123")

        assert result.cancel_requested_at is not None

    @pytest.mark.asyncio
    async def test_mark_multi_session_cancelled_sets_runtime_fields(self):
        mock_record = MagicMock()
        mock_record.session_id = "session-123"
        mock_record.status = "processing"
        mock_record.cancel_requested_at = None
        mock_record.cancelled_at = None
        mock_record.runtime_heartbeat_at = None

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=mock_record)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch("src.db.crud.get_session_maker", return_value=mock_session_maker):
            result = await mark_multi_session_cancelled(
                "session-123",
                progress={"completed": 1, "total": 3},
                result={"error": "Task cancelled by user"},
            )

        assert result.status == "cancelled"
        assert result.cancel_requested_at is not None
        assert result.cancelled_at is not None
        assert result.runtime_heartbeat_at is not None

    @pytest.mark.asyncio
    async def test_is_multi_session_cancel_requested_uses_db_state(self):
        mock_record = MagicMock()
        mock_record.status = "processing"
        mock_record.cancel_requested_at = datetime.now(timezone.utc)

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=mock_record)

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch("src.db.crud.get_session_maker", return_value=mock_session_maker):
            assert await is_multi_session_cancel_requested("session-123") is True

    @pytest.mark.asyncio
    async def test_touch_multi_session_runtime_heartbeat_updates_timestamp(self):
        mock_record = MagicMock()
        mock_record.status = "processing"
        mock_record.runtime_heartbeat_at = None

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=mock_record)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch("src.db.crud.get_session_maker", return_value=mock_session_maker):
            result = await touch_multi_session_runtime_heartbeat("session-123")

        assert result.runtime_heartbeat_at is not None


class TestCleanupCrud:
    """Tests for maintenance cleanup helpers."""

    @pytest.mark.asyncio
    async def test_find_analysis_cleanup_candidates_uses_expected_filters(self):
        mock_row = MagicMock(task_id="old-task")
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_row]

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars)

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch("src.db.crud.get_session_maker", return_value=mock_session_maker):
            rows = await find_analysis_cleanup_candidates(
                terminal_before=datetime(2024, 1, 1, tzinfo=timezone.utc),
                stale_processing_before=datetime(2024, 2, 1, tzinfo=timezone.utc),
                limit=10,
            )

            assert rows == [mock_row]
            mock_session.scalars.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_analyses_dry_run_does_not_delete(self):
        with patch(
            "src.db.crud.find_analysis_cleanup_candidates",
            new_callable=AsyncMock,
            return_value=[MagicMock(task_id="a"), MagicMock(task_id="b")],
        ):
            result = await cleanup_analyses(dry_run=True)

            assert result == {"count": 2, "task_ids": ["a", "b"], "deleted": False}

    @pytest.mark.asyncio
    async def test_cleanup_analyses_skips_processing_logic_when_no_candidates(self):
        with patch(
            "src.db.crud.find_analysis_cleanup_candidates",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await cleanup_analyses(dry_run=False)

            assert result == {"count": 0, "task_ids": [], "deleted": False}

    @pytest.mark.asyncio
    async def test_cleanup_multi_sessions_dry_run_does_not_delete(self):
        with patch(
            "src.db.crud.find_multi_session_cleanup_candidates",
            new_callable=AsyncMock,
            return_value=[MagicMock(session_id="s1")],
        ):
            result = await cleanup_multi_sessions(dry_run=True)

            assert result == {"count": 1, "session_ids": ["s1"], "deleted": False}

    @pytest.mark.asyncio
    async def test_find_multi_session_cleanup_candidates_uses_scalars(self):
        mock_row = MagicMock(session_id="old-session")
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_row]

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars)

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch("src.db.crud.get_session_maker", return_value=mock_session_maker):
            rows = await find_multi_session_cleanup_candidates(
                terminal_before=datetime(2024, 1, 1, tzinfo=timezone.utc),
                stale_processing_before=datetime(2024, 2, 1, tzinfo=timezone.utc),
                limit=10,
            )

            assert rows == [mock_row]
            mock_session.scalars.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_stale_analysis_runtime_candidates_uses_scalars(self):
        mock_row = MagicMock(task_id="stale-task")
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_row]

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars)

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch("src.db.crud.get_session_maker", return_value=mock_session_maker):
            rows = await find_stale_analysis_runtime_candidates(
                stale_before=datetime(2024, 2, 1, tzinfo=timezone.utc),
                limit=10,
            )

        assert rows == [mock_row]
        mock_session.scalars.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_stale_analyses_failed_merges_diagnostic_payload(self):
        stale_row = MagicMock()
        stale_row.task_id = "task-1"
        stale_row.status = "processing"
        stale_row.result = {"filename": "report.pdf"}
        stale_row.runtime_heartbeat_at = None

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [stale_row]

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars)
        mock_session.commit = AsyncMock()

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch("src.db.crud.find_stale_analysis_runtime_candidates", new_callable=AsyncMock, return_value=[stale_row]):
            with patch("src.db.crud.get_session_maker", return_value=mock_session_maker):
                result = await mark_stale_analyses_failed(
                    stale_before=datetime.now(timezone.utc),
                    dry_run=False,
                )

        assert result["updated"] is True
        assert stale_row.status == "failed"
        assert stale_row.result["filename"] == "report.pdf"
        assert stale_row.result["reason_code"] == "runtime_stale_timeout"

    @pytest.mark.asyncio
    async def test_find_stale_multi_session_runtime_candidates_uses_scalars(self):
        mock_row = MagicMock(session_id="stale-session")
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_row]

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars)

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch("src.db.crud.get_session_maker", return_value=mock_session_maker):
            rows = await find_stale_multi_session_runtime_candidates(
                stale_before=datetime(2024, 2, 1, tzinfo=timezone.utc),
                limit=10,
            )

        assert rows == [mock_row]
        mock_session.scalars.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_stale_multi_sessions_failed_merges_diagnostic_payload(self):
        stale_row = MagicMock()
        stale_row.session_id = "session-1"
        stale_row.status = "processing"
        stale_row.result = {"periods": [{"period_label": "2023"}]}
        stale_row.runtime_heartbeat_at = None

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [stale_row]

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars)
        mock_session.commit = AsyncMock()

        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager

        with patch("src.db.crud.find_stale_multi_session_runtime_candidates", new_callable=AsyncMock, return_value=[stale_row]):
            with patch("src.db.crud.get_session_maker", return_value=mock_session_maker):
                result = await mark_stale_multi_sessions_failed(
                    stale_before=datetime.now(timezone.utc),
                    dry_run=False,
                )

        assert result["updated"] is True
        assert stale_row.status == "failed"
        assert stale_row.result["periods"] == [{"period_label": "2023"}]
        assert stale_row.result["reason_code"] == "runtime_stale_timeout"
