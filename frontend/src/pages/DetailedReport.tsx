import React, { useCallback, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Card,
    Container,
    Group,
    Loader,
    Progress,
    SimpleGrid,
    Stack,
    Tabs,
    Text,
    ThemeIcon,
} from '@mantine/core';
import { BarChart } from '@mantine/charts';
import {
    Activity,
    AlertTriangle,
    BarChart3,
    PieChart,
    ShieldCheck,
    TrendingDown,
    TrendingUp,
    Wallet,
} from 'lucide-react';

import { AnalysisData, FinancialRatios } from '../api/interfaces';
import DetailedMetricsCard from '../components/report/DetailedMetricsCard';
import ReportHeader from '../components/report/ReportHeader';
import ScoreInsightsCard from '../components/report/ScoreInsightsCard';
import TrendChart from '../components/TrendChart';
import { LOW_CONFIDENCE_ALERT_THRESHOLD, REPORT_TOTAL_METRICS } from '../constants/report';
import { useMultiAnalysisPolling } from '../hooks/useMultiAnalysisPolling';
import { buildChartData } from '../utils/chartUtils';
import { countReliableMetrics } from '../utils/reliability';
import { generateTransactionId } from '../utils/transactionId';
export { THRESHOLDS, getBarColor, buildChartData } from '../utils/chartUtils';

interface DetailedReportProps {
    result: AnalysisData;
    filename?: string;
    multiSessionId?: string;
}

export const DetailedReport = ({ result, filename, multiSessionId }: DetailedReportProps) => {
    const transactionId = useMemo(() => generateTransactionId(), []);
    const chartData = useMemo(
        () => buildChartData(result.ratios ?? ({} as FinancialRatios)),
        [result.ratios]
    );
    const reliableCount = useMemo(
        () => countReliableMetrics(result.extraction_metadata),
        [result.extraction_metadata]
    );
    const { status: multiStatus, periods: multiData, progress: multiProgress } =
        useMultiAnalysisPolling(multiSessionId);

    const [selectedRatios, setSelectedRatios] = useState<string[]>([]);
    const handleRatioSelect = useCallback((key: string) => {
        setSelectedRatios((prev) =>
            prev.includes(key) ? prev.filter((ratio) => ratio !== key) : [...prev, key]
        );
    }, []);

    const handlePrint = () => window.print();

    const getTrend = (
        key: keyof typeof result.score.normalized_scores
    ): 'up' | 'down' | 'neutral' => {
        const value = result.score?.normalized_scores?.[key];
        if (value == null) {
            return 'neutral';
        }
        return value >= 0.6 ? 'up' : 'down';
    };

    const metricCards = [
        {
            label: 'Ликвидность',
            value: result?.ratios?.current_ratio != null ? result.ratios.current_ratio.toFixed(2) : '—',
            sub: 'Текущая',
            icon: Activity,
            trend: getTrend('current_ratio'),
            color: 'teal',
        },
        {
            label: 'Автономия',
            value: result?.ratios?.equity_ratio != null ? result.ratios.equity_ratio.toFixed(2) : '—',
            sub: 'Коэфф. собств. кап.',
            icon: ShieldCheck,
            trend: getTrend('equity_ratio'),
            color: 'blue',
        },
        {
            label: 'ROA',
            value: result?.ratios?.roa != null ? `${(result.ratios.roa * 100).toFixed(1)}%` : '—',
            sub: 'Рент. активов',
            icon: PieChart,
            trend: getTrend('roa'),
            color: 'indigo',
        },
        {
            label: 'ROE',
            value: result?.ratios?.roe != null ? `${(result.ratios.roe * 100).toFixed(1)}%` : '—',
            sub: 'Рент. капитала',
            icon: TrendingUp,
            trend: getTrend('roe'),
            color: 'violet',
        },
        {
            label: 'Фин. рычаг',
            value: result?.ratios?.financial_leverage != null
                ? result.ratios.financial_leverage.toFixed(2)
                : '—',
            sub: 'Финансовый рычаг',
            icon: BarChart3,
            trend: getTrend('financial_leverage'),
            color: 'orange',
        },
        {
            label: 'Маржа',
            value: (result?.metrics?.revenue != null && result?.metrics?.net_profit != null)
                ? `${((result.metrics.net_profit / result.metrics.revenue) * 100).toFixed(1)}%`
                : '—',
            sub: 'Чистая рентабельность',
            icon: Wallet,
            trend: (result?.metrics?.net_profit != null && result?.metrics?.revenue != null)
                ? (result.metrics.net_profit / result.metrics.revenue >= 0.05 ? 'up' : 'down')
                : 'neutral',
            color: 'cyan',
        },
    ];

    return (
        <Container size="xl" py="2rem">
            <Stack gap="xl">
                {result.score.confidence_score < LOW_CONFIDENCE_ALERT_THRESHOLD && (
                    <Alert
                        icon={<AlertTriangle size={20} />}
                        title="Низкая достоверность отчета"
                        color="orange"
                        variant="light"
                        radius="md"
                    >
                        Внимание! Отчет сформирован на основе неполных данных.
                        Достоверность: <b>{(result.score.confidence_score * 100).toFixed(0)}%</b>
                    </Alert>
                )}

                <ReportHeader
                    filename={filename}
                    transactionId={transactionId}
                    onPrint={handlePrint}
                />

                <Tabs defaultValue="overview">
                    <Tabs.List mb="xl">
                        <Tabs.Tab value="overview">Обзор</Tabs.Tab>
                        <Tabs.Tab value="dynamics">Динамика</Tabs.Tab>
                    </Tabs.List>

                    <Tabs.Panel value="overview">
                        <Stack gap="xl">
                            <ScoreInsightsCard score={result.score} />

                            <Card padding="xl" radius="md" shadow="sm" bg="white" style={{ border: 'none' }}>
                                <Text component="h3" size="xl" fw={700} mb="xl">
                                    Финансовые коэффициенты
                                </Text>
                                {chartData.length < 2 ? (
                                    <Text c="dimmed" ta="center" py="xl">
                                        Недостаточно данных для построения графика
                                    </Text>
                                ) : (
                                    <BarChart
                                        h={320}
                                        data={chartData.map((item) => ({
                                            label: item.label,
                                            value: item.value,
                                            color: item.color,
                                        }))}
                                        dataKey="label"
                                        series={[{ name: 'value', label: 'Значение' }]}
                                        withTooltip
                                        tooltipProps={{
                                            content: ({ payload }) => {
                                                if (!payload?.length) {
                                                    return null;
                                                }
                                                const item = payload[0];
                                                return (
                                                    <Box
                                                        p="xs"
                                                        bg="white"
                                                        style={{ border: '1px solid #e5e7eb', borderRadius: 8 }}
                                                    >
                                                        <Text size="xs" fw={700}>{item.payload?.label}</Text>
                                                        <Text size="xs">{Number(item.value).toFixed(2)}</Text>
                                                    </Box>
                                                );
                                            },
                                        }}
                                        gridAxis="y"
                                        barProps={{ radius: [4, 4, 0, 0] }}
                                    />
                                )}
                            </Card>

                            <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="xl">
                                {metricCards.map((metric, idx) => (
                                    <Card key={idx} padding="lg" radius="md" shadow="xs" bg="white" style={{ border: 'none' }}>
                                        <Group justify="space-between" mb="xs">
                                            <Text size="xs" fw={700} c="dimmed" tt="uppercase">{metric.label}</Text>
                                            <ThemeIcon variant="light" color={metric.color} size="md" radius="md">
                                                <metric.icon size={18} />
                                            </ThemeIcon>
                                        </Group>
                                        <Group align="flex-end" gap="xs">
                                            <Text size="xl" fw={800} style={{ fontFamily: 'JetBrains Mono' }}>
                                                {metric.value}
                                            </Text>
                                            {metric.trend !== 'neutral' && (
                                                <Group gap={2} c={metric.trend === 'up' ? 'teal' : 'red'}>
                                                    {metric.trend === 'up'
                                                        ? <TrendingUp size={14} />
                                                        : <TrendingDown size={14} />}
                                                </Group>
                                            )}
                                        </Group>
                                        <Text size="xs" c="dimmed" mt={4}>{metric.sub}</Text>
                                    </Card>
                                ))}
                            </SimpleGrid>

                            <DetailedMetricsCard
                                metrics={result.metrics}
                                extractionMetadata={result.extraction_metadata}
                                reliableCount={reliableCount}
                                totalMetrics={REPORT_TOTAL_METRICS}
                            />
                        </Stack>
                    </Tabs.Panel>

                    <Tabs.Panel value="dynamics">
                        <Card padding="xl" radius="md" shadow="sm" bg="white" style={{ border: 'none' }}>
                            {!multiSessionId && (
                                <Text c="dimmed" size="sm">
                                    Загрузите несколько отчётов для сравнения динамики по периодам.
                                </Text>
                            )}

                            {multiStatus === 'processing' && (
                                <Stack gap="md" align="center" py="xl">
                                    <Loader size="sm" />
                                    <Text size="sm" c="dimmed">Обработка периодов...</Text>
                                    {multiProgress && (
                                        <Stack gap="xs" w="100%" maw={400}>
                                            <Progress
                                                value={multiProgress.total > 0
                                                    ? (multiProgress.completed / multiProgress.total) * 100
                                                    : 0}
                                                animated
                                            />
                                            <Text size="xs" c="dimmed" ta="center">
                                                {multiProgress.completed} / {multiProgress.total} периодов
                                            </Text>
                                        </Stack>
                                    )}
                                </Stack>
                            )}

                            {multiStatus === 'failed' && (
                                <Text c="red" size="sm">
                                    Не удалось загрузить данные по периодам. Попробуйте повторить анализ.
                                </Text>
                            )}

                            {multiStatus === 'completed' && multiData && (
                                <TrendChart
                                    periods={multiData}
                                    selectedRatios={selectedRatios}
                                    onRatioSelect={handleRatioSelect}
                                    showTrendIndicators
                                />
                            )}
                        </Card>
                    </Tabs.Panel>
                </Tabs>
            </Stack>
        </Container>
    );
};
