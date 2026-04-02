import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MantineProvider } from '@mantine/core';
import TrendChart from '../TrendChart';
import { PeriodResult } from '../../api/interfaces';

// Wrapper component with MantineProvider
const wrapper = ({ children }: { children: React.ReactNode }) => (
    <MantineProvider>{children}</MantineProvider>
);

// Mock data factory
const createPeriodResult = (
    label: string,
    ratios: Record<string, number | null>
): PeriodResult => ({
    period_label: label,
    ratios,
    score: 75.0,
    risk_level: 'low',
    extraction_metadata: {},
});

describe('TrendChart', () => {
    describe('Rendering with null values', () => {
        it('renders without crashing when ratios contain null values', () => {
            const periods: PeriodResult[] = [
                createPeriodResult('2022', { roa: 0.1, roe: null }),
                createPeriodResult('2023', { roa: null, roe: 0.2 }),
            ];

            expect(() =>
                render(
                    <TrendChart
                        periods={periods}
                        selectedRatios={['roa', 'roe']}
                        onRatioSelect={vi.fn()}
                    />,
                    { wrapper }
                )
            ).not.toThrow();
        });

        it('does not call console.error when rendering null values', () => {
            const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => { });
            const periods: PeriodResult[] = [
                createPeriodResult('2021', { revenue: null, profit: null }),
                createPeriodResult('2022', { revenue: 1000, profit: null }),
                createPeriodResult('2023', { revenue: null, profit: 100 }),
            ];

            render(
                <TrendChart
                    periods={periods}
                    selectedRatios={['revenue', 'profit']}
                    onRatioSelect={vi.fn()}
                />,
                { wrapper }
            );

            expect(consoleErrorSpy).not.toHaveBeenCalled();
            consoleErrorSpy.mockRestore();
        });
    });

    describe('Empty data handling', () => {
        it('does not crash with empty periods array', () => {
            expect(() =>
                render(
                    <TrendChart
                        periods={[]}
                        selectedRatios={[]}
                        onRatioSelect={vi.fn()}
                    />,
                    { wrapper }
                )
            ).not.toThrow();
        });

        it('displays "no data" message when periods is empty', () => {
            render(
                <TrendChart
                    periods={[]}
                    selectedRatios={[]}
                    onRatioSelect={vi.fn()}
                />,
                { wrapper }
            );

            expect(screen.getByText('Нет данных для отображения')).toBeInTheDocument();
        });

        it('displays "select ratios" message when no ratios selected', () => {
            const periods: PeriodResult[] = [
                createPeriodResult('2023', { roa: 0.1, roe: 0.2 }),
            ];

            render(
                <TrendChart
                    periods={periods}
                    selectedRatios={[]}
                    onRatioSelect={vi.fn()}
                />,
                { wrapper }
            );

            expect(screen.getByText('Выберите показатели для отображения')).toBeInTheDocument();
        });
    });

    describe('Trend indicators', () => {
        it('shows trend direction arrows when showTrendIndicators is true', () => {
            const periods: PeriodResult[] = [
                createPeriodResult('2022', { roa: 0.1 }),
                createPeriodResult('2023', { roa: 0.15 }),
            ];

            render(
                <TrendChart
                    periods={periods}
                    selectedRatios={['roa']}
                    onRatioSelect={vi.fn()}
                    showTrendIndicators={true}
                />,
                { wrapper }
            );

            expect(screen.getByText('↑')).toBeInTheDocument();
        });

        it('shows down arrow for decreasing trend', () => {
            const periods: PeriodResult[] = [
                createPeriodResult('2022', { roa: 0.2 }),
                createPeriodResult('2023', { roa: 0.1 }),
            ];

            render(
                <TrendChart
                    periods={periods}
                    selectedRatios={['roa']}
                    onRatioSelect={vi.fn()}
                    showTrendIndicators={true}
                />,
                { wrapper }
            );

            expect(screen.getByText('↓')).toBeInTheDocument();
        });
    });

    describe('Anomaly detection', () => {
        it('shows warning icon for anomalous ratios', () => {
            const periods: PeriodResult[] = [
                createPeriodResult('2022', { roa: 0.1 }),
                createPeriodResult('2023', { roa: 0.9 }),
            ];

            render(
                <TrendChart
                    periods={periods}
                    selectedRatios={['roa']}
                    onRatioSelect={vi.fn()}
                    anomalyThreshold={0.5}
                />,
                { wrapper }
            );

            expect(screen.getByText('⚠')).toBeInTheDocument();
        });
    });

    describe('Checkbox interaction', () => {
        it('calls onRatioSelect when checkbox is clicked', async () => {
            const handleSelect = vi.fn();
            const periods: PeriodResult[] = [
                createPeriodResult('2023', { roa: 0.1 }),
            ];

            const user = await import('@testing-library/user-event').then(m => m.default);

            render(
                <TrendChart
                    periods={periods}
                    selectedRatios={[]}
                    onRatioSelect={handleSelect}
                />,
                { wrapper }
            );

            const checkbox = screen.getByLabelText('roa');
            await user.click(checkbox);

            expect(handleSelect).toHaveBeenCalledWith('roa');
        });
    });
});
