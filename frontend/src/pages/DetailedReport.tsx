import React, { useMemo, useState, useEffect, useCallback } from 'react';
import {
    Title, Text, Card, SimpleGrid, Stack, Group, Badge,
    Table, ThemeIcon, Button, Divider, Container, Box,
    Tabs, Progress, Loader, Alert, Tooltip
} from '@mantine/core';
// Импорт графиков
import { BarChart } from '@mantine/charts';
import {
    ShieldCheck, TrendingUp, TrendingDown, Activity,
    AlertTriangle, Printer, Download, PieChart,
    BarChart3, Wallet, Minus, Info
} from 'lucide-react';
import { AnalysisData, FinancialRatios } from '../api/interfaces';
import ConfidenceBadge from '../components/ConfidenceBadge';
import TrendChart from '../components/TrendChart';
import { useMultiAnalysisPolling } from '../hooks/useMultiAnalysisPolling';
import { buildChartData, getBarColor } from '../utils/chartUtils';

interface DetailedReportProps {
    result: AnalysisData;
    filename?: string;
    multiSessionId?: string;
}

// ---------------------------------------------------------------------------
// Confidence helpers
// ---------------------------------------------------------------------------

const CONFIDENCE_THRESHOLD = 0.5;
const TOTAL_METRICS = 15;

function countReliableMetrics(
    extractionMetadata: AnalysisData['extraction_metadata']
): number {
    if (!extractionMetadata) return 0;
    return Object.values(extractionMetadata).filter(
        (m) => m.confidence >= CONFIDENCE_THRESHOLD
    ).length;
}

export const DetailedReport = ({ result, filename, multiSessionId }: DetailedReportProps) => {
    const transactionId = useMemo(() =>
        Math.random().toString(36).substring(2, 11).toUpperCase(),
        []);

    // Build chart data from real ratios
    const chartData = useMemo(() => buildChartData(result.ratios ?? {} as FinancialRatios), [result.ratios]);

    // Confidence summary
    const reliableCount = useMemo(
        () => countReliableMetrics(result.extraction_metadata),
        [result.extraction_metadata]
    );

    // ---------------------------------------------------------------------------
    // Multi-period analysis state & polling
    // ---------------------------------------------------------------------------
    const { status: multiStatus, periods: multiData, progress: multiProgress } =
        useMultiAnalysisPolling(multiSessionId);

    const [selectedRatios, setSelectedRatios] = useState<string[]>([]);

    const handleRatioSelect = useCallback((key: string) => {
        setSelectedRatios((prev) =>
            prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
        );
    }, []);

    const getRiskColor = (risk: string) => {
        switch (risk) {
            case 'low': return '#00714d';
            case 'medium': return '#f59e0b';
            case 'high': return '#ba1a1a';
            case 'critical': return '#8b0000';
            default: return '#6b7280';
        }
    };

    const getRiskBg = (risk: string) => {
        switch (risk) {
            case 'low': return '#6cf8bb';
            case 'medium': return '#fef3c7';
            case 'high': return '#ffdad6';
            case 'critical': return '#ffd7d7';
            default: return '#f3f4f6';
        }
    };

    const handlePrint = () => window.print();

    // Derive trend direction from normalized_scores (>= 0.6 = positive/up, < 0.4 = negative/down)
    const getTrend = (key: keyof typeof result.score.normalized_scores): 'up' | 'down' | 'neutral' => {
        const val = result.score?.normalized_scores?.[key];
        if (val == null) return 'neutral';
        return val >= 0.6 ? 'up' : 'down';
    };

    const metrics = [
        {
            label: 'Ликвидность',
            value: result?.ratios?.current_ratio != null ? result.ratios.current_ratio.toFixed(2) : '—',
            sub: 'Текущая',
            icon: Activity,
            trend: getTrend('current_ratio'),
            color: 'teal'
        },
        {
            label: 'Автономия',
            value: result?.ratios?.equity_ratio != null ? result.ratios.equity_ratio.toFixed(2) : '—',
            sub: 'Коэфф. собств. кап.',
            icon: ShieldCheck,
            trend: getTrend('equity_ratio'),
            color: 'blue'
        },
        {
            label: 'ROA',
            value: result?.ratios?.roa != null ? (result.ratios.roa * 100).toFixed(1) + '%' : '—',
            sub: 'Рент. активов',
            icon: PieChart,
            trend: getTrend('roa'),
            color: 'indigo'
        },
        {
            label: 'ROE',
            value: result?.ratios?.roe != null ? (result.ratios.roe * 100).toFixed(1) + '%' : '—',
            sub: 'Рент. капитала',
            icon: TrendingUp,
            trend: getTrend('roe'),
            color: 'violet'
        },
        {
            label: 'Фин. рычаг',
            value: result?.ratios?.financial_leverage != null ? result.ratios.financial_leverage.toFixed(2) : '—',
            sub: 'Финансовый рычаг',
            icon: BarChart3,
            trend: getTrend('financial_leverage'),
            color: 'orange'
        },
        {
            label: 'Маржа',
            value: (result?.metrics?.revenue != null && result?.metrics?.net_profit != null)
                ? ((result.metrics.net_profit / result.metrics.revenue) * 100).toFixed(1) + '%'
                : '—',
            sub: 'Чистая рентабельность',
            icon: Wallet,
            trend: (result?.metrics?.net_profit != null && result?.metrics?.revenue != null)
                ? (result.metrics.net_profit / result.metrics.revenue >= 0.05 ? 'up' : 'down')
                : 'neutral',
            color: 'cyan'
        },
    ];

    return (
        <Container size="xl" py="2rem">
            <Stack gap="xl">
                {/* LOW CONFIDENCE ALERT */}
                {result.score.confidence_score < 0.6 && (
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

                {/* HEADER SECTION */}
                <Group justify="space-between" align="center">
                    <Stack gap={4}>
                        <Title order={1} style={{ letterSpacing: '-0.02em', fontWeight: 800 }}>
                            Отчет об анализе: {filename || 'Финансовый документ'}
                        </Title>
                        <Text c="dimmed" size="sm">ID Транзакции: {transactionId}</Text>
                    </Stack>
                    <Group gap="md">
                        <Button variant="subtle" leftSection={<Printer size={18} />} onClick={handlePrint} color="gray">
                            Печать
                        </Button>
                        <Button variant="filled" leftSection={<Download size={18} />} bg="#00288e">
                            Скачать PDF
                        </Button>
                    </Group>
                </Group>

                <Tabs defaultValue="overview">
                    <Tabs.List mb="xl">
                        <Tabs.Tab value="overview">Обзор</Tabs.Tab>
                        <Tabs.Tab value="dynamics">Динамика</Tabs.Tab>
                    </Tabs.List>

                    {/* ── TAB: Обзор ── */}
                    <Tabs.Panel value="overview">
                        <Stack gap="xl">

                            {/* SCORING & AI INSIGHTS */}
                            <Card padding="xl" radius="md" shadow="sm" bg="white" style={{ border: 'none' }}>
                                <SimpleGrid cols={{ base: 1, md: 2 }} spacing="2rem">
                                    <Stack justify="center" align="center" py="xl">
                                        <Text size="sm" fw={700} c="dimmed" tt="uppercase" lts="0.05em">Итоговый скоринг</Text>
                                        <Tooltip
                                            label={`Достоверность данных: ${(result.score.confidence_score * 100).toFixed(0)}%. Рассчитано на основе весов доступных коэффициентов.`}
                                            withArrow
                                            position="top"
                                        >
                                            <Title
                                                order={1}
                                                style={{
                                                    fontSize: '5rem',
                                                    fontFamily: 'JetBrains Mono',
                                                    color: getRiskColor(result.score.risk_level),
                                                    lineHeight: 1,
                                                    cursor: 'help'
                                                }}
                                            >
                                                {result.score.score}
                                            </Title>
                                        </Tooltip>
                                        <Badge
                                            size="xl" radius="xl" px="xl"
                                            style={{
                                                backgroundColor: getRiskBg(result.score.risk_level),
                                                color: getRiskColor(result.score.risk_level),
                                                border: 'none', fontWeight: 700
                                            }}
                                        >
                                            {result.score.risk_level === 'low'
                                                ? 'НИЗКИЙ РИСК'
                                                : result.score.risk_level === 'medium'
                                                    ? 'СРЕДНИЙ РИСК'
                                                    : result.score.risk_level === 'high'
                                                        ? 'ВЫСОКИЙ РИСК'
                                                        : 'КРИТИЧЕСКИЙ РИСК'}
                                        </Badge>
                                        <Text c="dimmed" size="sm" ta="center" mt="md" style={{ maxWidth: 300 }}>
                                            Компания демонстрирует {result.score.risk_level === 'low' ? 'стабильные' : 'требующие внимания'} показатели финансовой устойчивости.
                                        </Text>
                                    </Stack>

                                    <Stack gap="md">
                                        <Group gap="xs">
                                            <ThemeIcon variant="light" color="blue" radius="xl">
                                                <Activity size={16} />
                                            </ThemeIcon>
                                            <Title order={3}>AI-Инсайты и Аналитика</Title>
                                        </Group>
                                        <Divider variant="dashed" />
                                        <Text
                                            size="md"
                                            style={{
                                                lineHeight: 1.8,
                                                fontFamily: '"Libre Baskerville", serif',
                                                color: '#000000',
                                                textAlign: 'justify',
                                                letterSpacing: '-0.01em'
                                            }}
                                        >
                                            На основе глубокого анализа предоставленной финансовой отчетности, наша модель искусственного интеллекта выявила ключевые паттерны в структуре капитала.
                                            <br /><br />
                                            <b>Сильные стороны:</b> {result.score.factors.filter(f => f.impact === 'positive').map(f => f.name).join(', ') || 'Стабильность базовых метрик'}.
                                            <br />
                                            <b>Области внимания:</b> {result.score.factors.filter(f => f.impact === 'negative').map(f => f.name).join(', ') || 'Существенных рисков не обнаружено'}.
                                        </Text>

                                        {/* RISK FACTORS BLOCK */}
                                        <Stack gap="sm" mt="md">
                                            <Text fw={700} size="sm" tt="uppercase" c="dimmed" lts="0.05em">Факторы риска</Text>
                                            <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xs">
                                                {result.score.factors.map((factor, idx) => {
                                                    const isPositive = factor.impact === 'positive';
                                                    const isNegative = factor.impact === 'negative';
                                                    const color = isPositive ? 'teal' : isNegative ? 'red' : 'gray';
                                                    const Icon = isPositive ? TrendingUp : isNegative ? TrendingDown : Minus;

                                                    return (
                                                        <Card key={idx} withBorder padding="sm" radius="md" bg="#fcfcfc">
                                                            <Group gap="xs" wrap="nowrap" align="flex-start">
                                                                <ThemeIcon color={color} variant="light" size="sm" radius="xl">
                                                                    <Icon size={12} />
                                                                </ThemeIcon>
                                                                <Stack gap={2}>
                                                                    <Text size="xs" fw={700}>{factor.name}</Text>
                                                                    <Text size="xs" c="dimmed" style={{ lineHeight: 1.4 }}>{factor.description}</Text>
                                                                </Stack>
                                                            </Group>
                                                        </Card>
                                                    );
                                                })}
                                            </SimpleGrid>
                                        </Stack>
                                    </Stack>
                                </SimpleGrid>
                            </Card>

                            {/* VISUALIZATION SECTION — BarChart из реальных ratios */}
                            <Card padding="xl" radius="md" shadow="sm" bg="white" style={{ border: 'none' }}>
                                <Title order={3} mb="xl">Финансовые коэффициенты</Title>
                                {chartData.length < 2 ? (
                                    <Text c="dimmed" ta="center" py="xl">
                                        Недостаточно данных для построения графика
                                    </Text>
                                ) : (
                                    <BarChart
                                        h={320}
                                        data={chartData.map((d) => ({ label: d.label, value: d.value, color: d.color }))}
                                        dataKey="label"
                                        series={[{ name: 'value', label: 'Значение' }]}
                                        withTooltip
                                        tooltipProps={{
                                            content: ({ payload }) => {
                                                if (!payload?.length) return null;
                                                const item = payload[0];
                                                return (
                                                    <Box p="xs" bg="white" style={{ border: '1px solid #e5e7eb', borderRadius: 8 }}>
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

                            {/* FINANCIAL COEFFICIENTS GRID */}
                            <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="xl">
                                {metrics.map((m, i) => (
                                    <Card key={i} padding="lg" radius="md" shadow="xs" bg="white" style={{ border: 'none' }}>
                                        <Group justify="space-between" mb="xs">
                                            <Text size="xs" fw={700} c="dimmed" tt="uppercase">{m.label}</Text>
                                            <ThemeIcon variant="light" color={m.color} size="md" radius="md">
                                                <m.icon size={18} />
                                            </ThemeIcon>
                                        </Group>
                                        <Group align="flex-end" gap="xs">
                                            <Text size="xl" fw={800} style={{ fontFamily: 'JetBrains Mono' }}>{m.value}</Text>
                                            {m.trend !== 'neutral' && (
                                                <Group gap={2} c={m.trend === 'up' ? 'teal' : 'red'}>
                                                    {m.trend === 'up' ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                                                </Group>
                                            )}
                                        </Group>
                                        <Text size="xs" c="dimmed" mt={4}>{m.sub}</Text>
                                    </Card>
                                ))}
                            </SimpleGrid>

                            {/* DETAILED TABLE */}
                            <Card padding="xl" radius="md" shadow="sm" bg="white" style={{ border: 'none' }}>
                                <Title order={3} mb="xl">Детализированные показатели</Title>
                                <Table verticalSpacing="md" horizontalSpacing="md">
                                    <Table.Thead>
                                        <Table.Tr style={{ backgroundColor: '#f3f4f5' }}>
                                            <Table.Th style={{ border: 'none', borderRadius: '8px 0 0 8px' }}>Показатель</Table.Th>
                                            <Table.Th style={{ border: 'none' }} align="right">Значение</Table.Th>
                                            <Table.Th style={{ border: 'none' }} align="right">Уверенность</Table.Th>
                                            <Table.Th style={{ border: 'none', borderRadius: '0 8px 8px 0' }} align="right">Норматив</Table.Th>
                                        </Table.Tr>
                                    </Table.Thead>
                                    <Table.Tbody>
                                        {[
                                            { label: 'Выручка (Revenue)', val: result.metrics.revenue, unit: ' ₽', metricKey: 'revenue' },
                                            { label: 'Чистая прибыль (Net Profit)', val: result.metrics.net_profit, unit: ' ₽', bg: '#f8f9fa', metricKey: 'net_profit' },
                                            { label: 'Активы (Total Assets)', val: result.metrics.total_assets, unit: ' ₽', metricKey: 'total_assets' },
                                            { label: 'Собственный капитал (Equity)', val: result.metrics.equity, unit: ' ₽', bg: '#f8f9fa', metricKey: 'equity' }
                                        ].map((row, idx) => {
                                            const meta = result.extraction_metadata?.[row.metricKey];
                                            return (
                                                <Table.Tr key={idx} style={{ backgroundColor: row.bg || 'transparent' }}>
                                                    <Table.Td style={{ border: 'none' }}>{row.label}</Table.Td>
                                                    <Table.Td style={{ border: 'none', fontFamily: 'JetBrains Mono' }} align="right">
                                                        {row.val?.toLocaleString() || '—'}{row.unit}
                                                    </Table.Td>
                                                    <Table.Td style={{ border: 'none' }} align="right">
                                                        {meta ? (
                                                            <ConfidenceBadge
                                                                metricKey={row.metricKey}
                                                                confidence={meta.confidence}
                                                                source={meta.source}
                                                            />
                                                        ) : '—'}
                                                    </Table.Td>
                                                    <Table.Td style={{ border: 'none' }} align="right">—</Table.Td>
                                                </Table.Tr>
                                            );
                                        })}
                                    </Table.Tbody>
                                </Table>

                                {/* Confidence summary + hint */}
                                {result.extraction_metadata && (
                                    <Stack gap="xs" mt="md">
                                        <Text size="sm" c="dimmed">
                                            Извлечено надёжно: <b>{reliableCount} из {TOTAL_METRICS}</b> показателей
                                        </Text>
                                        <Group gap="xs" align="flex-start">
                                            <Info size={14} style={{ marginTop: 2, color: '#868e96', flexShrink: 0 }} />
                                            <Text size="xs" c="dimmed">
                                                Показатели с низкой уверенностью (красный индикатор) могут быть исключены из расчёта коэффициентов
                                            </Text>
                                        </Group>
                                    </Stack>
                                )}
                            </Card>
                        </Stack>
                    </Tabs.Panel>

                    {/* ── TAB: Динамика ── */}
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
