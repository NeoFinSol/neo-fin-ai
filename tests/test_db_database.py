"""Tests for database module."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.database import dispose_engine, get_engine, get_session, get_session_maker


class TestGetEngine:
    """Tests for get_engine function."""

    def test_first_call_creates_engine(self):
        """Test that first call creates engine."""
        with patch('src.db.database.create_async_engine') as mock_create, \
             patch('src.db.database.async_sessionmaker') as mock_maker, \
             patch('src.db.database._engine', None), \
             patch('src.db.database.AsyncSessionLocal', None):
            
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine
            
            result = get_engine()
            
            assert result is mock_engine
            mock_create.assert_called_once()
            mock_maker.assert_called_once()

    def test_subsequent_calls_return_cached_engine(self):
        """Test that subsequent calls return cached engine."""
        mock_cached_engine = MagicMock()
        
        with patch('src.db.database._engine', mock_cached_engine), \
             patch('src.db.database.AsyncSessionLocal', MagicMock()):
            
            result = get_engine()
            
            assert result is mock_cached_engine

    def test_engine_creation_error(self):
        """Test RuntimeError on engine creation failure."""
        with patch('src.db.database.create_async_engine', side_effect=Exception("DB connection failed")), \
             patch('src.db.database._engine', None):
            
            with pytest.raises(RuntimeError, match="Failed to create database engine"):
                get_engine()

    def test_default_database_url(self, monkeypatch):
        """Test get_engine uses DATABASE_URL from environment."""
        expected_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/neofin"

        import src.db.database as db_module
        original_engine = db_module._engine
        original_url = db_module.DATABASE_URL
        db_module._engine = None  # Reset to force re-creation
        db_module.DATABASE_URL = expected_url
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        try:
            with patch("src.db.database.create_async_engine") as mock_create:
                mock_create.return_value = MagicMock()
                get_engine()
                # Verify create_async_engine was called with the expected URL
                call_args = mock_create.call_args
                assert call_args[0][0] == expected_url
        finally:
            db_module._engine = original_engine  # Restore
            db_module.DATABASE_URL = original_url

    def test_testing_prefers_test_database_url(self, monkeypatch):
        """TESTING=1 should prefer TEST_DATABASE_URL to isolate test traffic."""
        expected_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/neofin_test"

        import src.db.database as db_module
        original_engine = db_module._engine
        original_url = db_module.DATABASE_URL
        db_module._engine = None
        db_module.DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/neofin"

        monkeypatch.setenv("TESTING", "1")
        monkeypatch.setenv("TEST_DATABASE_URL", expected_url)

        try:
            with patch("src.db.database.create_async_engine") as mock_create:
                mock_create.return_value = MagicMock()
                get_engine()
                assert mock_create.call_args[0][0] == expected_url
        finally:
            db_module._engine = original_engine
            db_module.DATABASE_URL = original_url

    def test_engine_uses_pool_timeout_and_recycle(self):
        """Configured pool timeout/recycle must be applied to the async engine."""
        import src.db.database as db_module

        original_engine = db_module._engine
        original_url = db_module.DATABASE_URL
        db_module._engine = None
        db_module.DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/neofin"

        try:
            with patch("src.db.database.create_async_engine") as mock_create, \
                 patch("src.db.database.async_sessionmaker") as mock_maker:
                mock_create.return_value = MagicMock()

                get_engine()

                kwargs = mock_create.call_args.kwargs
                assert kwargs["pool_timeout"] == 30
                assert kwargs["pool_recycle"] == 3600
                mock_maker.assert_called_once()
        finally:
            db_module._engine = original_engine
            db_module.DATABASE_URL = original_url


class TestGetSessionMaker:
    """Tests for get_session_maker function."""

    def test_returns_existing_maker(self):
        """Test returns existing session maker."""
        mock_maker = MagicMock(spec=async_sessionmaker)
        
        with patch('src.db.database.AsyncSessionLocal', mock_maker):
            result = get_session_maker()
            
            assert result is mock_maker

    def test_creates_engine_if_maker_none(self):
        """Test creates engine if maker is None."""
        mock_engine = MagicMock()
        mock_maker = MagicMock(spec=async_sessionmaker)
        
        with patch('src.db.database.AsyncSessionLocal', None), \
             patch('src.db.database._engine', None), \
             patch('src.db.database.create_async_engine', return_value=mock_engine), \
             patch('src.db.database.async_sessionmaker', return_value=mock_maker):
            
            result = get_session_maker()
            
            assert result is mock_maker
            mock_maker.assert_not_called()  # Maker was created, not called

    def test_runtime_error_on_failure(self):
        """Test RuntimeError if maker fails to initialize."""
        with patch('src.db.database.AsyncSessionLocal', None), \
             patch('src.db.database._engine', None), \
             patch('src.db.database.create_async_engine', side_effect=Exception("Failed")):
            
            with pytest.raises(RuntimeError, match="Failed to create database engine"):
                get_session_maker()


class TestGetSession:
    """Tests for get_session generator."""

    @pytest.mark.asyncio
    async def test_yields_session(self):
        """Test that generator yields session."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        mock_maker = MagicMock()
        mock_maker.return_value = mock_session
        
        with patch('src.db.database.get_session_maker', return_value=mock_maker):
            gen = get_session()
            result = await gen.__anext__()
            
            assert result is mock_session

    @pytest.mark.asyncio
    async def test_session_context_manager(self):
        """Test session properly uses context manager."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        mock_maker = MagicMock()
        mock_maker.return_value = mock_session
        
        with patch('src.db.database.get_session_maker', return_value=mock_maker):
            gen = get_session()
            await gen.__anext__()
            await gen.aclose()
            
            # Verify context manager was used
            mock_session.__aenter__.assert_called_once()
            mock_session.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_runtime_error_on_session_failure(self):
        """Test RuntimeError when session creation fails."""
        with patch('src.db.database.get_session_maker', side_effect=RuntimeError("Maker failed")):
            gen = get_session()
            
            with pytest.raises(RuntimeError, match="Failed to get database session"):
                await gen.__anext__()


class TestDisposeEngine:
    """Tests for dispose_engine function."""

    @pytest.mark.asyncio
    async def test_disposes_existing_engine(self):
        """Test disposes existing engine."""
        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock()
        
        with patch('src.db.database._engine', mock_engine), \
             patch('src.db.database.AsyncSessionLocal', MagicMock()):
            
            await dispose_engine()
            
            mock_engine.dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_noop_when_engine_none(self):
        """Test no operation when engine is None."""
        with patch('src.db.database._engine', None):
            # Should not raise
            await dispose_engine()

    @pytest.mark.asyncio
    async def test_resets_globals(self):
        """Test resets global variables."""
        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock()
        
        # Need to test actual module state
        import src.db.database as db_module
        
        original_engine = db_module._engine
        original_maker = db_module.AsyncSessionLocal
        
        try:
            db_module._engine = mock_engine
            db_module.AsyncSessionLocal = MagicMock()
            
            await dispose_engine()
            
            assert db_module._engine is None
            assert db_module.AsyncSessionLocal is None
        finally:
            # Restore original values
            db_module._engine = original_engine
            db_module.AsyncSessionLocal = original_maker
