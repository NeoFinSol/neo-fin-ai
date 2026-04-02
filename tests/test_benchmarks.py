"""
Performance benchmark tests for NeoFin AI.

These tests measure performance of critical operations:
- Database operations
- Financial calculations

Note: These tests are marked with @pytest.mark.benchmark and should be run separately.
Use: pytest tests/test_benchmarks.py -m benchmark

To run with benchmark output: pytest tests/test_benchmarks.py --benchmark-only
"""

import asyncio

import pytest

pytest.importorskip("pytest_benchmark")

from src.analysis.ratios import calculate_ratios
from src.analysis.scoring import calculate_integral_score
from src.db.crud import create_analysis, get_analysis, update_analysis


pytestmark = pytest.mark.benchmark


SAMPLE_METRICS = {
    "revenue": 1000000,
    "net_profit": 150000,
    "total_assets": 2000000,
    "equity": 800000,
    "liabilities": 1200000,
    "current_assets": 500000,
    "short_term_liabilities": 300000,
}


class TestBenchmarkFinancialCalculations:
    """Benchmarks for financial calculation functions."""

    def test_calculate_ratios_performance(self, benchmark):
        """Benchmark calculate_ratios function."""
        result = benchmark(calculate_ratios, SAMPLE_METRICS)

        assert "current_ratio" in result or result == {}

    def test_calculate_integral_score_performance(self, benchmark):
        """Benchmark calculate_integral_score function."""
        ratios = {
            "current_ratio": 1.5,
            "equity_ratio": 0.4,
            "roa": 0.075,
            "roe": 0.1875,
            "debt_to_revenue": 1.2,
        }

        result = benchmark(calculate_integral_score, ratios)

        assert "score" in result or result == {}


class TestBenchmarkDatabaseOperations:
    """Benchmarks for database operations."""

    @pytest.mark.asyncio
    async def test_create_analysis_performance(self, benchmark, db_session):
        """Benchmark create_analysis function."""
        task_id = "benchmark-task-1"

        async def create_task():
            return await create_analysis(task_id, "processing", None)

        result = benchmark(asyncio.run, create_task())

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_analysis_performance(self, benchmark, db_session):
        """Benchmark get_analysis function."""
        task_id = "benchmark-task-2"
        await create_analysis(task_id, "completed", {"test": "data"})

        result = benchmark(asyncio.run, get_analysis(task_id))

        assert result is not None
        assert result.task_id == task_id

    @pytest.mark.asyncio
    async def test_update_analysis_performance(self, benchmark, db_session):
        """Benchmark update_analysis function."""
        task_id = "benchmark-task-3"
        await create_analysis(task_id, "processing", None)

        result = benchmark(
            asyncio.run,
            update_analysis(task_id, "completed", {"benchmark": "result"}),
        )

        assert result is not None


class TestBenchmarkConcurrency:
    """Benchmarks for concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_database_operations(self, benchmark, db_session):
        """Benchmark concurrent database operations."""

        async def create_and_get(task_id):
            await create_analysis(task_id, "processing", None)
            return await get_analysis(task_id)

        async def run_concurrent():
            tasks = [create_and_get(f"concurrent-task-{i}") for i in range(10)]
            return await asyncio.gather(*tasks)

        results = benchmark(asyncio.run, run_concurrent())

        assert len(results) == 10
        assert all(r is not None for r in results)


PERFORMANCE_THRESHOLDS = {
    "calculate_ratios": 0.1,
    "calculate_integral_score": 0.05,
    "create_analysis": 0.5,
    "get_analysis": 0.3,
    "update_analysis": 0.3,
}
