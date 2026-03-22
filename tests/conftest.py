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
