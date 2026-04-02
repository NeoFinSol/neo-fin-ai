from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from src.exceptions import DatabaseError
from src.routers.multi_analysis import get_multi_analysis_status


@pytest.mark.asyncio
async def test_get_multi_analysis_status_db_failure_raises_database_error():
    """DB lookup failures must not be downgraded to not-found responses."""
    async def _auth_ok() -> str:
        return "test-key"

    with patch(
        "src.routers.multi_analysis.get_multi_session",
        new_callable=AsyncMock,
        side_effect=SQLAlchemyError("db down"),
    ):
        with pytest.raises(DatabaseError):
            await get_multi_analysis_status("session-123", _api_key=await _auth_ok())


@pytest.mark.asyncio
async def test_get_multi_analysis_status_still_returns_404_for_missing_session():
    """Missing rows should keep the existing 404 contract."""
    async def _auth_ok() -> str:
        return "test-key"

    with patch(
        "src.routers.multi_analysis.get_multi_session",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_multi_analysis_status("missing-session", _api_key=await _auth_ok())

    assert exc_info.value.status_code == 404
