import { describe, it, expect } from 'vitest';
import { buildChartData, getBarColor, THRESHOLDS } from '../DetailedReport';
import { FinancialRatios } from '../../api/interfaces';

describe('DetailedReport - Pure Functions', () => {
    describe('buildChartData', () => {
        it('builds chart data from ratios with non-zero values', () => {
            const ratios = {
                current_ratio: 2.5,
                quick_ratio: 0,
                roa: 0.08,
                roe: null,
            } as FinancialRatios;

            const data = buildChartData(ratios);

            expect(data).toHaveLength(2);
            expect(data.map(d => d.key)).toContain('current_ratio');
            expect(data.map(d => d.key)).toContain('roa');
            expect(data.map(d => d.key)).not.toContain('quick_ratio');
            expect(data.map(d => d.key)).not.toContain('roe');
        });

        it('returns empty array for empty ratios', () => {
            const data = buildChartData({} as FinancialRatios);
            expect(data).toHaveLength(0);
        });

        it('returns empty array for all null/zero ratios', () => {
            const ratios = {
                current_ratio: 0,
                quick_ratio: null,
                roa: 0,
            } as FinancialRatios;

            const data = buildChartData(ratios);
            expect(data).toHaveLength(0);
        });

        it('includes label for each ratio', () => {
            const ratios = { current_ratio: 2.5 } as FinancialRatios;
            const data = buildChartData(ratios);

            expect(data[0].label).toBe('Тек. ликвидность');
        });

        it('includes color for each ratio', () => {
            const ratios = { current_ratio: 2.5 } as FinancialRatios;
            const data = buildChartData(ratios);

            expect(data[0].color).toBeDefined();
            expect(typeof data[0].color).toBe('string');
        });

        it('includes value for each ratio', () => {
            const ratios = { current_ratio: 2.5 } as FinancialRatios;
            const data = buildChartData(ratios);

            expect(data[0].value).toBe(2.5);
        });

        it('includes only non-zero non-null values', () => {
            const ratios = {
                current_ratio: 2.5,
                quick_ratio: 0,
                roa: -0.05,
                roe: null,
            } as FinancialRatios;

            const data = buildChartData(ratios);

            // Only current_ratio should be included (non-zero, non-null)
            expect(data).toHaveLength(2);
            expect(data.map(d => d.key)).toContain('current_ratio');
            expect(data.map(d => d.key)).toContain('roa');
        });

        it('handles all ratio types', () => {
            const ratios = {
                current_ratio: 2.5,
                quick_ratio: 1.5,
                absolute_liquidity_ratio: 0.5,
                roa: 0.08,
                roe: 0.15,
                ros: 0.1,
                ebitda_margin: 0.2,
                equity_ratio: 0.6,
                financial_leverage: 0.4,
                interest_coverage: 5.0,
                asset_turnover: 0.8,
                inventory_turnover: 6.0,
                receivables_turnover: 8.0,
            } as FinancialRatios;

            const data = buildChartData(ratios);
            expect(data.length).toBeGreaterThan(0);
        });
    });

    describe('getBarColor', () => {
        it('returns teal for value above threshold', () => {
            const color = getBarColor('current_ratio', 2.5);
            expect(color).toBe('teal.6');
        });

        it('returns red for value below threshold', () => {
            const color = getBarColor('current_ratio', 1.5);
            expect(color).toBe('red.5');
        });

        it('returns blue for ratio without threshold', () => {
            const color = getBarColor('asset_turnover', 0.5);
            expect(color).toBe('blue.6');
        });

        it('uses correct thresholds for different ratios', () => {
            // current_ratio threshold = 2.0
            expect(getBarColor('current_ratio', 2.5)).toBe('teal.6');
            expect(getBarColor('current_ratio', 1.5)).toBe('red.5');

            // quick_ratio threshold = 1.0
            expect(getBarColor('quick_ratio', 1.5)).toBe('teal.6');
            expect(getBarColor('quick_ratio', 0.5)).toBe('red.5');

            // roa threshold = 0.05
            expect(getBarColor('roa', 0.08)).toBe('teal.6');
            expect(getBarColor('roa', 0.03)).toBe('red.5');

            // roe threshold = 0.10
            expect(getBarColor('roe', 0.15)).toBe('teal.6');
            expect(getBarColor('roe', 0.05)).toBe('red.5');

            // equity_ratio threshold = 0.5
            expect(getBarColor('equity_ratio', 0.6)).toBe('teal.6');
            expect(getBarColor('equity_ratio', 0.3)).toBe('red.5');
        });

        it('handles edge case at threshold', () => {
            // At exact threshold should be teal (>=)
            expect(getBarColor('current_ratio', 2.0)).toBe('teal.6');
            expect(getBarColor('roa', 0.05)).toBe('teal.6');
        });
    });

    describe('THRESHOLDS', () => {
        it('has threshold for current_ratio', () => {
            expect(THRESHOLDS.current_ratio).toBe(2.0);
        });

        it('has threshold for quick_ratio', () => {
            expect(THRESHOLDS.quick_ratio).toBe(1.0);
        });

        it('has threshold for roa', () => {
            expect(THRESHOLDS.roa).toBe(0.05);
        });

        it('has threshold for roe', () => {
            expect(THRESHOLDS.roe).toBe(0.10);
        });

        it('has threshold for equity_ratio', () => {
            expect(THRESHOLDS.equity_ratio).toBe(0.5);
        });

        it('does not have threshold for all ratios', () => {
            // Some ratios don't have thresholds
            expect(THRESHOLDS.asset_turnover).toBeUndefined();
            expect(THRESHOLDS.inventory_turnover).toBeUndefined();
            expect(THRESHOLDS.receivables_turnover).toBeUndefined();
        });
    });

    describe('RATIO_LABELS mapping', () => {
        it('buildChartData uses correct labels', () => {
            const ratios = { current_ratio: 2.5 } as FinancialRatios;
            const data = buildChartData(ratios);
            
            expect(data[0].label).toBe('Тек. ликвидность');
        });

        it('buildChartData handles unknown ratio keys', () => {
            const ratios = { unknown_ratio: 1.5 } as any;
            const data = buildChartData(ratios);
            
            // Should use the key as label if no label mapping exists
            expect(data[0].label).toBe('unknown_ratio');
        });
    });
});
