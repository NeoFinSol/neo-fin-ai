/**
 * Tests for DetailedReport chart helpers
 * Feature: analysis-history-visualization
 * Requirements: 5.1, 5.2, 5.3, 5.7
 */
import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { buildChartData, getBarColor, THRESHOLDS, DetailedReport } from '../DetailedReport';
import type { FinancialRatios, AnalysisData } from '../../api/interfaces';

// ---------------------------------------------------------------------------
// Arbitrary: generates a FinancialRatios-shaped object with random values
// Each key maps to a number | null (including 0 to test filtering)
// ---------------------------------------------------------------------------

const RATIO_KEYS: Array<keyof FinancialRatios> = [
    'current_ratio',
    'quick_ratio',
    'absolute_liquidity_ratio',
    'roa',
    'roe',
    'ros',
    'ebitda_margin',
    'equity_ratio',
    'financial_leverage',
    'interest_coverage',
    'asset_turnover',
    'inventory_turnover',
    'receivables_turnover',
];

// Generates a value that can be: null, 0, or a non-zero float
const ratioValueArb = fc.oneof(
    fc.constant(null),
    fc.constant(0),
    fc.float({ min: -100, max: 100, noNaN: true }).filter((v) => v !== 0),
);

const ratiosArbitrary: fc.Arbitrary<FinancialRatios> = fc
    .record(
        Object.fromEntries(RATIO_KEYS.map((k) => [k, ratioValueArb])) as Record<
            keyof FinancialRatios,
            fc.Arbitrary<number | null>
        >,
    )
    .map((r) => r as FinancialRatios);

// ---------------------------------------------------------------------------
// Property 8: Данные BarChart из реальных ratios
// Feature: analysis-history-visualization, Property 8: данные BarChart из реальных ratios
// Validates: Requirements 5.1, 5.2
// ---------------------------------------------------------------------------

describe('buildChartData — property-based tests', () => {
    it('Property 8: length equals non-zero, non-null count (100 iterations)', () => {
        fc.assert(
            fc.property(ratiosArbitrary, (ratios) => {
                const chartData = buildChartData(ratios);
                const nonZeroCount = RATIO_KEYS.filter((k) => {
                    const v = ratios[k];
                    return v !== null && v !== 0;
                }).length;
                expect(chartData.length).toBe(nonZeroCount);
            }),
            { numRuns: 100 },
        );
    });

    it('Property 8: each point has a string label and numeric value', () => {
        fc.assert(
            fc.property(ratiosArbitrary, (ratios) => {
                const chartData = buildChartData(ratios);
                for (const point of chartData) {
                    expect(typeof point.label).toBe('string');
                    expect(point.label.length).toBeGreaterThan(0);
                    expect(typeof point.value).toBe('number');
                    expect(isFinite(point.value)).toBe(true);
                }
            }),
            { numRuns: 100 },
        );
    });

    it('Property 8: each point color matches getBarColor(key, value)', () => {
        fc.assert(
            fc.property(ratiosArbitrary, (ratios) => {
                const chartData = buildChartData(ratios);
                for (const point of chartData) {
                    const expected = getBarColor(point.key as keyof FinancialRatios, point.value);
                    expect(point.color).toBe(expected);
                }
            }),
            { numRuns: 100 },
        );
    });

    it('returns empty array for all-null ratios', () => {
        const allNull = Object.fromEntries(RATIO_KEYS.map((k) => [k, null])) as FinancialRatios;
        expect(buildChartData(allNull)).toEqual([]);
    });

    it('returns empty array for all-zero ratios', () => {
        const allZero = Object.fromEntries(RATIO_KEYS.map((k) => [k, 0])) as unknown as FinancialRatios;
        expect(buildChartData(allZero)).toEqual([]);
    });

    it('returns all keys when all values are non-zero', () => {
        const allNonZero = Object.fromEntries(RATIO_KEYS.map((k) => [k, 1.5])) as unknown as FinancialRatios;
        expect(buildChartData(allNonZero).length).toBe(RATIO_KEYS.length);
    });
});

// ---------------------------------------------------------------------------
// Property 9: Цветовое кодирование столбцов
// Feature: analysis-history-visualization, Property 9: цветовое кодирование столбцов
// Validates: Requirements 5.7
// ---------------------------------------------------------------------------

const thresholdKeyArb = fc.constantFrom(
    ...(Object.keys(THRESHOLDS) as Array<keyof FinancialRatios>),
);

const ratioWithThresholdArb = thresholdKeyArb.chain((key) =>
    fc
        .float({ min: -10, max: 20, noNaN: true })
        .map((value) => ({ key, value, threshold: THRESHOLDS[key]! })),
);

describe('getBarColor — property-based tests', () => {
    it('Property 9: teal.6 when value >= threshold, red.5 otherwise (100 iterations)', () => {
        fc.assert(
            fc.property(ratioWithThresholdArb, ({ key, value, threshold }) => {
                const color = getBarColor(key, value);
                if (value >= threshold) {
                    expect(color).toBe('teal.6');
                } else {
                    expect(color).toBe('red.5');
                }
            }),
            { numRuns: 100 },
        );
    });

    it('returns blue.6 for keys without a defined threshold', () => {
        expect(getBarColor('ros', 0.5)).toBe('blue.6');
        expect(getBarColor('financial_leverage', 2.0)).toBe('blue.6');
    });

    it('returns teal.6 when value equals threshold exactly', () => {
        for (const [key, threshold] of Object.entries(THRESHOLDS) as Array<[keyof FinancialRatios, number]>) {
            expect(getBarColor(key, threshold)).toBe('teal.6');
        }
    });
});

// ---------------------------------------------------------------------------
// Task 8.4: Unit-тест: < 2 ненулевых коэффициентов → "Недостаточно данных"
// Feature: analysis-history-visualization
// Validates: Requirement 5.3
// ---------------------------------------------------------------------------

/** Minimal valid AnalysisData with overridable ratios */
function makeResult(ratios: Partial<FinancialRatios> = {}): AnalysisData {
    const nullRatios: FinancialRatios = {
        current_ratio: null, quick_ratio: null, absolute_liquidity_ratio: null,
        roa: null, roe: null, ros: null, ebitda_margin: null,
        equity_ratio: null, financial_leverage: null, interest_coverage: null,
        asset_turnover: null, inventory_turnover: null, receivables_turnover: null,
    };
    return {
        scanned: false,
        text: '',
        tables: [],
        metrics: {
            revenue: null, net_profit: null, total_assets: null, equity: null,
            liabilities: null, current_assets: null, short_term_liabilities: null,
            accounts_receivable: null, inventory: null, cash_and_equivalents: null,
            ebitda: null, ebit: null, interest_expense: null,
            cost_of_goods_sold: null, average_inventory: null,
        },
        ratios: { ...nullRatios, ...ratios },
        score: {
            score: 50,
            risk_level: 'medium',
            factors: [],
            normalized_scores: {},
        },
        nlp: { risks: [], key_factors: [], recommendations: [] },
    };
}

function renderReport(ratios: Partial<FinancialRatios> = {}) {
    return render(
        <MantineProvider>
            <DetailedReport result={makeResult(ratios)} filename="test.pdf" />
        </MantineProvider>,
    );
}

const INSUFFICIENT = 'Недостаточно данных для построения графика';

describe('DetailedReport — insufficient data message (Requirement 5.3)', () => {
    it('shows message when ratios is empty (all null)', () => {
        renderReport({});
        expect(screen.getByText(INSUFFICIENT)).toBeInTheDocument();
    });

    it('shows message when only one non-zero ratio is present', () => {
        renderReport({ roa: 0.08 });
        expect(screen.getByText(INSUFFICIENT)).toBeInTheDocument();
    });

    it('does NOT show message when two non-zero ratios are present', () => {
        renderReport({ roa: 0.08, roe: 0.12 });
        expect(screen.queryByText(INSUFFICIENT)).not.toBeInTheDocument();
    });

    it('shows message when all ratios are zero', () => {
        renderReport({ current_ratio: 0, roa: 0 });
        expect(screen.getByText(INSUFFICIENT)).toBeInTheDocument();
    });
});
