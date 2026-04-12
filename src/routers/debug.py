from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.core.auth import get_api_key
from src.db import crud

router = APIRouter(tags=["debug"])


@router.get("/debug/decision-trace/{task_id}")
async def get_decision_trace(
    task_id: str,
    api_key: str = Depends(get_api_key),
) -> dict:
    analysis = await crud.get_analysis(task_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    result = analysis.result or {}
    trace = result.get("decision_trace")
    return {"task_id": task_id, "decision_trace": trace}
