import React, { useMemo } from 'react';
import { LineChart } from '@mantine/charts';
import { Checkbox, Group, Stack, Text } from '@mantine/core';
import { PeriodResult } from '../api/interfaces';

interface TrendChartProps {
    periods: PeriodResult[];
    selectedRatios: string[];
    onRatioSelect: (key: string) => void;
    anomalyThreshold?: number;
    showTrendIndicators?: boolean;
}

type ChartRow = Record<string, string | number | null>;
type TrendDirection = '↑' | '↓' | '';

const SERIES_COLORS = [
    'blue.6', 'red.6', 'green.6', 'orange.6', 'violet.6',
    'cyan.6', 'pink.6', 'teal.6', 'yellow.6', 'indigo.6',
] as const;

// Pure: derive sorted union of all ratio keys across periods
function collectRatioKeys(periods: PeriodResult[]): string[] {
    const keys = new Set<string>();
    for (const p of periods) {
        for (const k of Object.keys(p.ratios)) {
            keys.add(k);
        }
    }
    return Array.from(keys).sort();
}

// Pure: build chart dataset — null preserved for gap rendering
function buildChartData(periods: PeriodResult[], selectedRatios: string[]): ChartRow[] {
    return periods.map((p) => {
        const row: ChartRow = { period: p.period_label };
        for (const key of selectedRatios) {
            const val = p.ratios[key];
            // undefined (key absent) and null both become null — no coercion to 0
            row[key] = val !== undefined ? val : null;
        }
        return row;
    });
}

// Pure: compare last two non-null values; returns '' if fewer than 2 exist
function getTrendDirection(periods: PeriodResult[], ratioKey: string): TrendDirection {
    const values = periods
        .map((p) => p.ratios[ratioKey])
        .filter((v): v is number => typeof v === 'number' && isFinite(v));
    if (values.length < 2) return '';
    const last = values[values.length - 1];
    const prev = values[values.length - 2];
    if (last > prev) return '↑';
    if (last < prev) return '↓';
    return '';
}

// Pure: returns set of ratio keys where abs(delta of last two values) > threshold
function detectAnomalies(
    periods: PeriodResult[],
    ratioKeys: string[],
    threshold: number,
): Set<string> {
    const anomalies = new Set<string>();
    for (const key of ratioKeys) {
        const values = periods
            .map((p) => p.ratios[key])
            .filter((v): v is number => typeof v === 'number' && isFinite(v));
        if (values.length < 2) continue;
        const delta = Math.abs(values[values.length - 1] - values[values.length - 2]);
        if (delta > threshold) anomalies.add(key);
    }
    return anomalies;
}

const TrendChart: React.FC<TrendChartProps> = ({
    periods,
    selectedRatios,
    onRatioSelect,
    anomalyThreshold,
    showTrendIndicators = false,
}) => {
    const allKeys = useMemo(() => collectRatioKeys(periods), [periods]);

    const chartData = useMemo(
        () => buildChartData(periods, selectedRatios),
        [periods, selectedRatios],
    );

    const series = useMemo(
        () => selectedRatios.map((key, i) => ({
            name: key,
            color: SERIES_COLORS[i % SERIES_COLORS.length],
        })),
        [selectedRatios],
    );

    // Map ratio key → color name (without weight suffix) for legend text
    const colorMap = useMemo(
        () => Object.fromEntries(
            selectedRatios.map((key, i) => [
                key,
                SERIES_COLORS[i % SERIES_COLORS.length].split('.')[0],
            ]),
        ),
        [selectedRatios],
    );

    const trendMap = useMemo((): Record<string, TrendDirection> => {
        if (!showTrendIndicators) return {};
        return Object.fromEntries(
            selectedRatios.map((key) => [key, getTrendDirection(periods, key)]),
        );
    }, [periods, selectedRatios, showTrendIndicators]);

    const anomalies = useMemo(
        () =>
            anomalyThreshold !== undefined
                ? detectAnomalies(periods, selectedRatios, anomalyThreshold)
                : new Set<string>(),
        [periods, selectedRatios, anomalyThreshold],
    );

    const showLegendRow =
        selectedRatios.length > 0 && (showTrendIndicators || anomalyThreshold !== undefined);

    if (periods.length === 0) {
        return <Text c="dimmed" size="sm">Нет данных для отображения</Text>;
    }

    return (
        <Stack gap="md">
            {/* Ratio selector */}
            <Group gap="xs" wrap="wrap">
                {allKeys.map((key) => (
                    <Checkbox
                        key={key}
                        label={key}
                        checked={selectedRatios.includes(key)}
                        onChange={() => onRatioSelect(key)}
                        size="xs"
                    />
                ))}
            </Group>

            {/* Trend + anomaly legend row */}
            {showLegendRow && (
                <Group gap="sm" wrap="wrap">
                    {selectedRatios.map((key) => {
                        const direction = trendMap[key] ?? '';
                        const isAnomaly = anomalies.has(key);
                        return (
                            <Text key={key} size="xs" c={colorMap[key]}>
                                {key}
                                {direction !== '' && (
                                    <Text span c={direction === '↑' ? 'green' : 'red'} fw={700} ml={4}>
                                        {direction}
                                    </Text>
                                )}
                                {isAnomaly && (
                                    <Text span c="orange" fw={700} ml={4} title="Аномальное изменение">
                                        ⚠
                                    </Text>
                                )}
                            </Text>
                        );
                    })}
                </Group>
            )}

            {/* Chart */}
            {selectedRatios.length > 0 ? (
                <LineChart
                    h={300}
                    data={chartData}
                    dataKey="period"
                    series={series}
                    connectNulls={false}
                    withLegend={false}
                    withTooltip
                    withDots
                    curveType="linear"
                    xAxisLabel="Период"
                    yAxisLabel="Значение"
                />
            ) : (
                <Text c="dimmed" size="sm">Выберите показатели для отображения</Text>
            )}
        </Stack>
    );
};

export default TrendChart;
