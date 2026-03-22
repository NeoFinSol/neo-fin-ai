from __future__ import annotations

import uuid

import pytest

from src.db.crud import create_analysis, get_analysis, update_analysis


@pytest.mark.asyncio
async def test_analysis_crud_roundtrip(db_session):
    task_id = f"task-{uuid.uuid4().hex}"

    created = await create_analysis(task_id, "processing", None)
    assert created.task_id == task_id
    assert created.status == "processing"

    fetched = await get_analysis(task_id)
    assert fetched is not None
    assert fetched.task_id == task_id

    await update_analysis(task_id, "completed", {"data": {"score": 88}})

    updated = await get_analysis(task_id)
    assert updated is not None
    assert updated.status == "completed"
    assert updated.result == {"data": {"score": 88}}
