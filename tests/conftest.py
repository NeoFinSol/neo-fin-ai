from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# =============================================================================
# CRITICAL: Set environment variables BEFORE any app imports
# This must be at module level, not in a fixture, to ensure app_settings
# picks up the correct values when the app module is imported.
# =============================================================================
os.environ["TESTING"] = "1"
os.environ["DEV_MODE"] = "1"
os.environ["API_KEY"] = "test-key-for-testing"

import src.db.crud as crud
import src.db.database as db
from src.db.database import Base


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--run-pdf-real-heavy",
        action="store_true",
        default=False,
        help="Run the optional heavy real-PDF regression tier.",
    )


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test (requires full app setup)"
    )
    config.addinivalue_line(
        "markers",
        "benchmark: mark test as performance benchmark (slow, run separately)",
    )
    config.addinivalue_line(
        "markers", "frontend: mark test as frontend integration test"
    )
    config.addinivalue_line(
        "markers", "pdf_real: mark test as real-PDF smoke regression corpus"
    )
    config.addinivalue_line(
        "markers",
        "pdf_real_heavy: mark test as optional heavy real-PDF regression corpus",
    )


@pytest.fixture(autouse=True, scope="session")
def setup_test_environment():
    """
    Setup test environment for all tests.
    This fixture runs automatically before any tests.
    """
    # Environment already set at module level
    yield
    # Cleanup
    os.environ.pop("DEV_MODE", None)
    os.environ.pop("API_KEY", None)
    os.environ.pop("TESTING", None)


@pytest.fixture(scope="function")
def dev_mode_enabled(monkeypatch):
    """
    Fixture to enable DEV_MODE for specific tests that need to bypass authentication.
    """
    monkeypatch.setenv("DEV_MODE", "1")
    yield
    monkeypatch.delenv("DEV_MODE", raising=False)


@pytest.fixture(scope="function")
def auth_enabled(monkeypatch):
    """
    Fixture to ensure authentication is enabled for tests.
    Sets DEV_MODE=0 and requires API_KEY to be set.
    """
    monkeypatch.setenv("DEV_MODE", "0")
    monkeypatch.setenv("API_KEY", "test-api-key-for-testing")
    yield


@pytest.fixture(scope="function")
def client(db_engine, monkeypatch):
    """
    Create test client with authentication properly configured.

    This fixture:
    1. Imports app AFTER environment variables are set
    2. Overrides auth dependency to bypass authentication
    3. Returns configured TestClient

    Usage:
        def test_endpoint(client):
            response = client.get("/endpoint")
    """
    engine, _schema = db_engine
    session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    monkeypatch.setattr(db, "AsyncSessionLocal", session_maker)
    monkeypatch.setattr(db, "get_session_maker", lambda: session_maker)
    monkeypatch.setattr(crud, "get_session_maker", lambda: session_maker)

    from fastapi.testclient import TestClient

    from src.app import app
    from src.core.auth import get_api_key

    # Override auth dependency to always return test user
    async def override_auth():
        return "test-user"

    app.dependency_overrides[get_api_key] = override_auth

    with TestClient(app) as test_client:
        yield test_client

    # Cleanup
    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def db_engine():
    base_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not base_url:
        pytest.skip("TEST_DATABASE_URL or DATABASE_URL is not set")

    schema = f"test_{uuid.uuid4().hex}"

    base_engine = create_async_engine(base_url, future=True)
    async with base_engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    await base_engine.dispose()

    url = make_url(base_url)
    engine = create_async_engine(
        url,
        future=True,
        connect_args={"server_settings": {"search_path": schema}},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine, schema

    async with base_engine.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    await engine.dispose()
    await base_engine.dispose()


@pytest_asyncio.fixture()
async def db_session(db_engine, monkeypatch):
    engine, _schema = db_engine
    session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    monkeypatch.setattr(db, "AsyncSessionLocal", session_maker)
    monkeypatch.setattr(db, "get_session_maker", lambda: session_maker)
    monkeypatch.setattr(crud, "get_session_maker", lambda: session_maker)

    async with session_maker() as session:
        yield session


@pytest.fixture
def benchmark():
    """Minimal local benchmark fallback when pytest-benchmark plugin is absent."""

    def runner(func, *args, **kwargs):
        return func(*args, **kwargs)

    return runner
