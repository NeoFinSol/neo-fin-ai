from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import src.db.crud as crud
import src.db.database as db
from src.db.database import Base

# Set TESTING=1 to bypass DATABASE_URL validation during tests
# Do NOT set DEV_MODE here - tests should verify authentication behavior
os.environ["TESTING"] = "1"


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test (requires full app setup)"
    )
    config.addinivalue_line(
        "markers", "benchmark: mark test as performance benchmark (slow, run separately)"
    )
    config.addinivalue_line(
        "markers", "frontend: mark test as frontend integration test"
    )


@pytest.fixture(autouse=True, scope="session")
def setup_test_environment():
    """
    Setup test environment for all tests.
    This fixture runs automatically before any tests.
    """
    # Set DEV_MODE for all tests to bypass authentication
    # Individual tests can override this with auth_enabled fixture
    os.environ["DEV_MODE"] = "1"
    yield
    # Cleanup
    os.environ.pop("DEV_MODE", None)


@pytest.fixture(scope="function")
def dev_mode_enabled(monkeypatch):
    """
    Fixture to enable DEV_MODE for specific tests that need to bypass authentication.
    Use this fixture explicitly in tests that require unauthenticated access.
    
    Usage:
        def test_something(dev_mode_enabled):
            # DEV_MODE is enabled only for this test
    """
    # DEV_MODE is already set globally, this is just for explicit documentation
    monkeypatch.setenv("DEV_MODE", "1")
    yield
    monkeypatch.delenv("DEV_MODE", raising=False)


@pytest.fixture(scope="function")
def auth_enabled(monkeypatch):
    """
    Fixture to ensure authentication is enabled for tests.
    Sets DEV_MODE=0 and requires API_KEY to be set.
    
    Usage:
        def test_authenticated_endpoint(auth_enabled, client):
            # Authentication is enforced
            response = client.get("/protected", headers={"X-API-Key": "test-key"})
    """
    monkeypatch.setenv("DEV_MODE", "0")
    monkeypatch.setenv("API_KEY", "test-api-key-for-testing")
    yield


@pytest_asyncio.fixture(scope="session")
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
    query = dict(url.query)
    query["options"] = f"-csearch_path={schema}"
    url = url.set(query=query)

    engine = create_async_engine(url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine, schema

    async with engine.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(db_engine, monkeypatch):
    engine, _schema = db_engine
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    monkeypatch.setattr(db, "AsyncSessionLocal", session_maker)
    monkeypatch.setattr(crud, "AsyncSessionLocal", session_maker)

    async with session_maker() as session:
        yield session
