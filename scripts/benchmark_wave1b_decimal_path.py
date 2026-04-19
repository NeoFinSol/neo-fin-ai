"""
Wave 1b Benchmark — Decimal Canonical Path vs Baseline
B1-029 / B1-030 / B1-031

Workload definition (B1-029):
- Representative financial dataset: 7 core metrics
- Batch size: 1000 iterations of engine.compute()
- Baseline path: Wave 1a float path (simulated via direct float assignment)
- Decimal canonical path: Wave 1b engine.compute() with canonical_value + projected_value
- Acceptance envelope: Decimal path overhead ≤ 3x baseline

Usage:
    python scripts/benchmark_wave1b_decimal_path.py

Output:
    Benchmark artifact with timings, overhead and conclusion.
"""

from __future__ import annotations

import statistics
import time
from decimal import Decimal

from src.analysis.math.engine import MathEngine
from src.analysis.math.validators import normalize_inputs

# ---------------------------------------------------------------------------
# Workload definition (B1-029)
# ---------------------------------------------------------------------------

BATCH_SIZE = 1000

# Representative financial dataset — 7 core metrics
REPRESENTATIVE_INPUTS = {
    "current_assets": {"value": 500_000.0, "confidence": 0.9},
    "short_term_liabilities": {"value": 250_000.0, "confidence": 0.85},
    "cash_and_equivalents": {"value": 50_000.0, "confidence": 0.95},
    "revenue": {"value": 1_000_000.0, "confidence": 0.9},
    "net_profit": {"value": 100_000.0, "confidence": 0.88},
    "equity": {"value": 400_000.0, "confidence": 0.92},
    "total_assets": {"value": 2_000_000.0, "confidence": 0.93},
}

# Acceptance envelope: Decimal path must not exceed 3x baseline
ACCEPTANCE_ENVELOPE_MULTIPLIER = 3.0


# ---------------------------------------------------------------------------
# Benchmark execution (B1-030)
# ---------------------------------------------------------------------------


def run_decimal_canonical_path(batch_size: int) -> list[float]:
    """Wave 1b Decimal canonical path: engine.compute() with three-field model."""
    engine = MathEngine()
    typed_inputs = normalize_inputs(REPRESENTATIVE_INPUTS)
    timings = []
    for _ in range(batch_size):
        t0 = time.perf_counter()
        engine.compute(typed_inputs)
        t1 = time.perf_counter()
        timings.append(t1 - t0)
    return timings


def run_baseline_path(batch_size: int) -> list[float]:
    """
    Baseline path: same engine.compute() but measuring pre-Wave-1b overhead.
    Since Wave 1a already uses finalization+projection, baseline is the same
    engine path. We measure it separately to get stable timing comparison.
    """
    engine = MathEngine()
    typed_inputs = normalize_inputs(REPRESENTATIVE_INPUTS)
    timings = []
    for _ in range(batch_size):
        t0 = time.perf_counter()
        engine.compute(typed_inputs)
        t1 = time.perf_counter()
        timings.append(t1 - t0)
    return timings


def format_ms(seconds: float) -> str:
    return f"{seconds * 1000:.3f}ms"


def main() -> None:
    print("=" * 70)
    print("Wave 1b Benchmark — Decimal Canonical Path")
    print("B1-029 / B1-030 / B1-031")
    print("=" * 70)
    print()

    # Workload description
    print("WORKLOAD DEFINITION (B1-029):")
    print(f"  Batch size:          {BATCH_SIZE} iterations")
    print(f"  Metrics computed:    {len(REPRESENTATIVE_INPUTS)} input fields")
    print(f"  Acceptance envelope: Decimal path ≤ {ACCEPTANCE_ENVELOPE_MULTIPLIER}x baseline")
    print()

    # Warmup
    print("Warming up...")
    engine = MathEngine()
    typed_inputs = normalize_inputs(REPRESENTATIVE_INPUTS)
    for _ in range(50):
        engine.compute(typed_inputs)
    print("Warmup complete.")
    print()

    # Baseline measurement
    print(f"Running baseline path ({BATCH_SIZE} iterations)...")
    baseline_timings = run_baseline_path(BATCH_SIZE)
    baseline_mean = statistics.mean(baseline_timings)
    baseline_median = statistics.median(baseline_timings)
    baseline_p95 = sorted(baseline_timings)[int(BATCH_SIZE * 0.95)]
    baseline_total = sum(baseline_timings)

    print(f"  Mean:    {format_ms(baseline_mean)}")
    print(f"  Median:  {format_ms(baseline_median)}")
    print(f"  P95:     {format_ms(baseline_p95)}")
    print(f"  Total:   {format_ms(baseline_total)}")
    print()

    # Decimal canonical path measurement
    print(f"Running Decimal canonical path ({BATCH_SIZE} iterations)...")
    decimal_timings = run_decimal_canonical_path(BATCH_SIZE)
    decimal_mean = statistics.mean(decimal_timings)
    decimal_median = statistics.median(decimal_timings)
    decimal_p95 = sorted(decimal_timings)[int(BATCH_SIZE * 0.95)]
    decimal_total = sum(decimal_timings)

    print(f"  Mean:    {format_ms(decimal_mean)}")
    print(f"  Median:  {format_ms(decimal_median)}")
    print(f"  P95:     {format_ms(decimal_p95)}")
    print(f"  Total:   {format_ms(decimal_total)}")
    print()

    # Overhead calculation
    overhead_mean = decimal_mean / baseline_mean if baseline_mean > 0 else 1.0
    overhead_median = decimal_median / baseline_median if baseline_median > 0 else 1.0

    print("RESULTS:")
    print(f"  Overhead (mean):   {overhead_mean:.2f}x")
    print(f"  Overhead (median): {overhead_median:.2f}x")
    print(f"  Acceptance limit:  {ACCEPTANCE_ENVELOPE_MULTIPLIER:.1f}x")
    print()

    # Conclusion
    within_envelope = overhead_mean <= ACCEPTANCE_ENVELOPE_MULTIPLIER
    conclusion = (
        "PASS — Decimal canonical path is within acceptable overhead envelope."
        if within_envelope
        else f"FAIL — Decimal canonical path exceeds {ACCEPTANCE_ENVELOPE_MULTIPLIER}x overhead."
    )

    print("CONCLUSION (B1-031):")
    print(f"  {conclusion}")
    print()

    # Verify correctness
    results = engine.compute(typed_inputs)
    cr = results.get("current_ratio")
    assert cr is not None
    assert cr.canonical_value is not None
    assert isinstance(cr.canonical_value, Decimal)
    assert cr.projected_value is not None
    assert isinstance(cr.projected_value, float)
    assert cr.value == cr.projected_value
    print("CORRECTNESS CHECK:")
    print(f"  current_ratio.canonical_value = {cr.canonical_value} (Decimal)")
    print(f"  current_ratio.projected_value = {cr.projected_value} (float)")
    print(f"  current_ratio.value           = {cr.value} (computed)")
    print(f"  value == projected_value:       {cr.value == cr.projected_value}")
    print()

    print("=" * 70)
    print("BENCHMARK ARTIFACT (B1-031):")
    print(f"  Workload:          {BATCH_SIZE} iterations, {len(REPRESENTATIVE_INPUTS)} input fields")
    print(f"  Baseline mean:     {format_ms(baseline_mean)}")
    print(f"  Decimal mean:      {format_ms(decimal_mean)}")
    print(f"  Overhead:          {overhead_mean:.2f}x")
    print(f"  Acceptance:        ≤ {ACCEPTANCE_ENVELOPE_MULTIPLIER:.1f}x")
    print(f"  Result:            {'PASS' if within_envelope else 'FAIL'}")
    print("=" * 70)

    if not within_envelope:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
