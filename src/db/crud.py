from __future__ import annotations

from sqlalchemy import select

from src.db.database import AsyncSessionLocal
from src.db.models import Analysis


async def create_analysis(task_id: str, status: str, result: dict | None = None) -> Analysis:
    async with AsyncSessionLocal() as session:
        analysis = Analysis(task_id=task_id, status=status, result=result)
        session.add(analysis)
        await session.commit()
        await session.refresh(analysis)
        return analysis


async def update_analysis(task_id: str, status: str, result: dict | None = None) -> Analysis | None:
    async with AsyncSessionLocal() as session:
        stmt = select(Analysis).where(Analysis.task_id == task_id)
        existing = await session.scalar(stmt)
        if existing is None:
            return None
        existing.status = status
        existing.result = result
        await session.commit()
        await session.refresh(existing)
        return existing


async def get_analysis(task_id: str) -> Analysis | None:
    async with AsyncSessionLocal() as session:
        stmt = select(Analysis).where(Analysis.task_id == task_id)
        return await session.scalar(stmt)
