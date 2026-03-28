"""
Router for analysis history endpoints.
Feature: analysis-history-visualization
Requirements: 1.1–1.7, 2.1–2.5
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from src.core.auth import get_api_key
from src.db.crud import get_analyses_list, get_analysis
from src.exceptions import DatabaseError
from src.models.schemas import (
    AnalysisDetailResponse,
    AnalysisListResponse,
    AnalysisSummaryResponse,
)
from src.utils.masking import mask_analysis_data

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyses", tags=["analyses"])


def _prefer_scalar(value, fallback):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return fallback


def _is_demo_mode() -> bool:
    return os.getenv("DEMO_MODE") == "1"


@router.get("", response_model=AnalysisListResponse)
async def list_analyses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _api_key: str = Depends(get_api_key),
) -> AnalysisListResponse:
    """Return paginated list of analyses ordered by created_at DESC."""
    try:
        items, total = await get_analyses_list(page, page_size)
    except SQLAlchemyError as exc:
        logger.error("Failed to list analyses: %s", exc)
        raise DatabaseError("Database operation failed") from exc
    demo = _is_demo_mode()

    summary_items: list[AnalysisSummaryResponse] = []
    for a in items:
        result = a.result or {}
        masked = mask_analysis_data(result, demo)
        data = masked.get("data") or {}
        score_block = data.get("score") or {}
        score = _prefer_scalar(getattr(a, "score", None), score_block.get("score"))
        risk_level = _prefer_scalar(
            getattr(a, "risk_level", None),
            score_block.get("risk_level"),
        )
        filename = _prefer_scalar(getattr(a, "filename", None), masked.get("filename"))

        summary_items.append(
            AnalysisSummaryResponse(
                task_id=a.task_id,
                status=a.status,
                created_at=a.created_at,
                score=score,
                risk_level=risk_level,
                filename=filename,
            )
        )

    return AnalysisListResponse(
        items=summary_items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{task_id}", response_model=AnalysisDetailResponse)
async def get_analysis_detail(
    task_id: str,
    _api_key: str = Depends(get_api_key),
) -> AnalysisDetailResponse:
    """Return full analysis data for a given task_id."""
    try:
        analysis = await get_analysis(task_id)
    except SQLAlchemyError as exc:
        logger.error("Failed to load analysis detail for %s: %s", task_id, exc)
        raise DatabaseError("Database operation failed") from exc
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    demo = _is_demo_mode()
    masked = mask_analysis_data(analysis.result or {}, demo)

    return AnalysisDetailResponse(
        task_id=analysis.task_id,
        status=analysis.status,
        created_at=analysis.created_at,
        data=masked.get("data") if isinstance(masked, dict) else None,
    )
