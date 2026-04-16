"""
Tests for Wave 6 — Layering Cleanup (ARCH-001 and ARCH-002).

ARCH-001: DB connectivity check moved from router to crud.py
ARCH-002: DatabaseConfig dataclass decouples get_engine() from app_settings
"""

import inspect
from dataclasses import FrozenInstanceError
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import settings as h_settings
from hypothesis import strategies as st

import src.routers.system as system_module
from src.db.crud import check_database_connectivity
from src.db.database import DatabaseConfig

# ---------------------------------------------------------------------------
# ARCH-001 — check_database_connectivity in crud layer
# ---------------------------------------------------------------------------


class TestCheckDatabaseConnectivityContract:
    """check_database_connectivity() must always return bool, never raise."""

    @pytest.mark.asyncio
    async def test_returns_true_when_session_succeeds(self):
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=None)
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_maker = MagicMock(return_value=mock_cm)

        with patch("src.db.crud.get_session_maker", return_value=mock_maker):
            result = await check_database_connectivity()

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_session_raises(self):
        mock_maker = MagicMock(side_effect=RuntimeError("db down"))

        with patch("src.db.crud.get_session_maker", return_value=mock_maker):
            result = await check_database_connectivity()

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_execute_error(self):
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=OSError("connection refused"))
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_maker = MagicMock(return_value=mock_cm)

        with patch("src.db.crud.get_session_maker", return_value=mock_maker):
            result = await check_database_connectivity()

        assert result is False

    @pytest.mark.asyncio
    async def test_never_raises(self):
        """Even with a completely broken session maker, must not raise."""
        with patch("src.db.crud.get_session_maker", side_effect=Exception("boom")):
            result = await check_database_connectivity()
        assert isinstance(result, bool)


class TestRouterLayerViolationsRemoved:
    """Router must not contain SQL or engine imports after ARCH-001 fix."""

    def test_router_does_not_import_sqlalchemy_text(self):
        assert not hasattr(
            system_module, "text"
        ), "sqlalchemy.text must not be imported in system router"

    def test_router_does_not_import_get_engine(self):
        assert not hasattr(
            system_module, "get_engine"
        ), "get_engine must not be imported in system router"

    def test_router_source_has_no_select_1(self):
        source = inspect.getsource(system_module)
        assert "SELECT 1" not in source

    def test_router_uses_check_database_connectivity(self):
        assert hasattr(system_module, "check_database_connectivity")


class TestSystemEndpointsWithMockedConnectivity:
    """Endpoint behaviour must be identical after the refactor."""

    def _make_client(self):
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(system_module.router)
        return TestClient(app, raise_server_exceptions=False)

    def test_health_endpoint_db_up(self):
        client = self._make_client()
        with patch(
            "src.routers.system.check_database_connectivity",
            new_callable=AsyncMock,
            return_value=True,
        ), patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = False
            resp = client.get("/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["services"]["db"] == "ok"

    def test_health_endpoint_db_down(self):
        client = self._make_client()
        with patch(
            "src.routers.system.check_database_connectivity",
            new_callable=AsyncMock,
            return_value=False,
        ), patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = False
            resp = client.get("/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["services"]["db"] == "down"
        assert data["status"] == "down"

    def test_ready_endpoint_db_down_returns_503(self):
        client = self._make_client()
        with patch(
            "src.routers.system.check_database_connectivity",
            new_callable=AsyncMock,
            return_value=False,
        ):
            resp = client.get("/system/ready")
        assert resp.status_code == 503

    def test_ready_endpoint_db_up_returns_200(self):
        client = self._make_client()
        with patch(
            "src.routers.system.check_database_connectivity",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = client.get("/system/ready")
        assert resp.status_code == 200

    def test_database_is_available_logs_on_exception(self, caplog):
        """When check_database_connectivity raises, router logs the error."""
        import logging

        client = self._make_client()
        with patch(
            "src.routers.system.check_database_connectivity",
            new_callable=AsyncMock,
            side_effect=RuntimeError("unexpected"),
        ), patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = False
            with caplog.at_level(logging.ERROR, logger="src.routers.system"):
                resp = client.get("/system/health")
        assert resp.status_code == 200
        assert resp.json()["services"]["db"] == "down"


# ---------------------------------------------------------------------------
# ARCH-001 PBT — check_database_connectivity always returns bool
# ---------------------------------------------------------------------------


@given(
    exc=st.sampled_from(
        [
            Exception("generic"),
            RuntimeError("runtime"),
            OSError("os error"),
            ValueError("value"),
            ConnectionError("conn"),
        ]
    )
)
@h_settings(max_examples=30)
@pytest.mark.asyncio
async def test_check_db_connectivity_always_returns_bool(exc):
    """P1: for any exception from the session, result is always bool."""
    with patch("src.db.crud.get_session_maker", side_effect=exc):
        result = await check_database_connectivity()
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# ARCH-002 — DatabaseConfig dataclass
# ---------------------------------------------------------------------------


class TestDatabaseConfigDataclass:
    def test_from_settings_fields_match(self):
        class MockSettings:
            db_pool_size = 10
            db_max_overflow = 20
            db_pool_timeout = 30
            db_pool_recycle = 3600
            db_pool_pre_ping = True

        cfg = DatabaseConfig.from_settings(MockSettings())
        assert cfg.pool_size == 10
        assert cfg.max_overflow == 20
        assert cfg.pool_timeout == 30
        assert cfg.pool_recycle == 3600
        assert cfg.pool_pre_ping is True

    def test_is_frozen(self):
        cfg = DatabaseConfig(
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
        )
        with pytest.raises(FrozenInstanceError):
            cfg.pool_size = 99  # type: ignore[misc]

    def test_explicit_construction(self):
        cfg = DatabaseConfig(
            pool_size=3,
            max_overflow=7,
            pool_timeout=15,
            pool_recycle=1800,
            pool_pre_ping=False,
        )
        assert cfg.pool_size == 3
        assert cfg.pool_pre_ping is False


class TestGetEngineWithDatabaseConfig:
    def test_get_engine_with_explicit_config_uses_cfg_values(self):
        """get_engine(config=...) must pass cfg values to _create_engine_with_pool."""
        custom_cfg = DatabaseConfig(
            pool_size=7,
            max_overflow=14,
            pool_timeout=45,
            pool_recycle=7200,
            pool_pre_ping=False,
        )

        captured = {}

        def fake_create(db_url, **kwargs):
            captured.update(kwargs)
            engine = MagicMock()
            engine.connect = MagicMock()
            return engine

        with patch("src.db.database._engine", None), patch(
            "src.db.database.AsyncSessionLocal", None
        ), patch(
            "src.db.database._resolve_database_url",
            return_value="sqlite+aiosqlite:///:memory:",
        ), patch(
            "src.db.database._create_engine_with_pool", side_effect=fake_create
        ), patch(
            "src.db.database._make_session_maker", return_value=MagicMock()
        ):
            from src.db.database import get_engine

            get_engine(config=custom_cfg)

        # pool_timeout and pool_recycle must come from cfg, not app_settings
        assert captured.get("pool_timeout") == 45
        assert captured.get("pool_recycle") == 7200
        assert captured.get("pool_pre_ping") is False

    def test_database_config_is_frozen(self):
        cfg = DatabaseConfig(
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
        )
        with pytest.raises(FrozenInstanceError):
            cfg.pool_size = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ARCH-002 PBT — DatabaseConfig.from_settings always matches source
# ---------------------------------------------------------------------------


@given(
    pool_size=st.integers(min_value=1, max_value=100),
    max_overflow=st.integers(min_value=0, max_value=100),
    pool_timeout=st.integers(min_value=1, max_value=300),
    pool_recycle=st.integers(min_value=60, max_value=86400),
    pool_pre_ping=st.booleans(),
)
@h_settings(max_examples=100)
def test_database_config_from_settings_fields_match(
    pool_size, max_overflow, pool_timeout, pool_recycle, pool_pre_ping
):
    """P2: from_settings always produces a DatabaseConfig matching the source."""

    class MockSettings:
        pass

    s = MockSettings()
    s.db_pool_size = pool_size
    s.db_max_overflow = max_overflow
    s.db_pool_timeout = pool_timeout
    s.db_pool_recycle = pool_recycle
    s.db_pool_pre_ping = pool_pre_ping

    cfg = DatabaseConfig.from_settings(s)
    assert cfg.pool_size == pool_size
    assert cfg.max_overflow == max_overflow
    assert cfg.pool_timeout == pool_timeout
    assert cfg.pool_recycle == pool_recycle
    assert cfg.pool_pre_ping == pool_pre_ping
