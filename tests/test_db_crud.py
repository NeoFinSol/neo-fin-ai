"""Tests for database CRUD operations."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.db.crud import create_analysis, get_analysis, update_analysis


class TestCreateAnalysis:
    """Tests for create_analysis function."""

    @pytest.mark.asyncio
    async def test_successful_creation(self):
        """Test successful analysis creation."""
        mock_session = AsyncMock()
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
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_analysis = MagicMock()
        result_data = {"score": 85.5, "metrics": {"revenue": 100}}
        
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

    @pytest.mark.asyncio
    async def test_sqlalchemy_error_handling(self):
        """Test SQLAlchemyError handling."""
        mock_session = AsyncMock()
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
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

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
        """Test updating only status field."""
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
            assert mock_existing.result is None  # Result also updated to None

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
    async def test_get_sqlalchemy_error_returns_none(self):
        """Test SQLAlchemyError returns None (graceful degradation)."""
        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(side_effect=SQLAlchemyError("Connection error"))
        
        mock_session_maker = MagicMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_context_manager
        
        with patch('src.db.crud.get_session_maker', return_value=mock_session_maker):
            result = await get_analysis("test-123")
            
            # get_analysis swallows exceptions and returns None
            assert result is None
