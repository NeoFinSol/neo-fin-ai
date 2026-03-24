"""
Property-based and unit tests for get_analyses_list in src/db/crud.py
Feature: analysis-history-visualization
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.db.crud import get_analyses_list


# ---------------------------------------------------------------------------
# Strategy helpers
# ---------------------------------------------------------------------------

def _make_analysis(task_id: str | None = None, created_at: datetime | None = None) -> MagicMock:
    """Build a mock Analysis ORM object."""
    obj = MagicMock()
    obj.task_id = task_id or str(uuid.uuid4())
    obj.status = "completed"
    obj.result = None
    obj.created_at = created_at or datetime.now(timezone.utc)
    return obj


def analysis_strategy():
    """Hypothesis strategy that produces mock Analysis objects."""
    return st.builds(
        lambda tid: _make_analysis(task_id=tid),
        tid=st.uuids().map(str),
    )


def _mock_session_for(items: list, total: int):
    """Return a patched get_session_maker that yields (items, total)."""
    scalars_result = MagicMock()
    scalars_result.all.return_value = items

    mock_session = AsyncMock()
    mock_session.scalars = AsyncMock(return_value=scalars_result)
    mock_session.scalar = AsyncMock(return_value=total)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_maker = MagicMock(return_value=mock_ctx)
    return mock_maker


# ---------------------------------------------------------------------------
# Property 3: Корректность пагинации CRUD
# Validates: Requirements 1.3, 1.8
# ---------------------------------------------------------------------------

@given(
    page=st.integers(min_value=1, max_value=10),
    page_size=st.integers(min_value=1, max_value=100),
    all_items=st.lists(analysis_strategy(), min_size=0, max_size=200),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_get_analyses_list_pagination(page, page_size, all_items):
    # Feature: analysis-history-visualization, Property 3: корректность пагинации CRUD
    # Validates: Requirements 1.3, 1.8
    total = len(all_items)
    offset = (page - 1) * page_size
    page_items = all_items[offset: offset + page_size]

    mock_maker = _mock_session_for(page_items, total)

    with patch("src.db.crud.get_session_maker", return_value=mock_maker):
        items, returned_total = await get_analyses_list(page, page_size)

    # total must equal the overall record count
    assert returned_total == total, (
        f"Expected total={total}, got {returned_total}"
    )
    # page slice must not exceed page_size
    assert len(items) <= page_size, (
        f"Expected len(items) <= {page_size}, got {len(items)}"
    )
    # page slice must match the expected window
    assert len(items) == len(page_items), (
        f"Expected {len(page_items)} items for page={page}, page_size={page_size}, "
        f"total={total}; got {len(items)}"
    )


# ---------------------------------------------------------------------------
# Unit tests
# Validates: Requirements 1.8
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_db_returns_empty_list_and_zero():
    mock_maker = _mock_session_for([], 0)
    with patch("src.db.crud.get_session_maker", return_value=mock_maker):
        items, total = await get_analyses_list(1, 20)
    assert items == []
    assert total == 0


@pytest.mark.asyncio
async def test_single_record_returns_one_item():
    analysis = _make_analysis()
    mock_maker = _mock_session_for([analysis], 1)
    with patch("src.db.crud.get_session_maker", return_value=mock_maker):
        items, total = await get_analyses_list(1, 20)
    assert len(items) == 1
    assert total == 1
    assert items[0].task_id == analysis.task_id


@pytest.mark.asyncio
async def test_page_beyond_data_returns_empty_items_with_correct_total():
    # Page 5 of a 3-record DB → empty items, but total still 3
    mock_maker = _mock_session_for([], 3)
    with patch("src.db.crud.get_session_maker", return_value=mock_maker):
        items, total = await get_analyses_list(5, 20)
    assert items == []
    assert total == 3
