import React, { useMemo } from 'react';
import {
    Title, Text, Card, SimpleGrid, Stack, Group, Badge,
    Table, ThemeIcon, Button, Divider, Container, Box
} from '@mantine/core';
// Импорт графиков
import { LineChart, BarChart } from '@mantine/charts';
import {
    ShieldCheck, TrendingUp, TrendingDown, Activity,
    AlertTriangle, Printer, Download, PieChart,
    BarChart3, Wallet, Minus
} from 'lucide-react';
import { useLocation, Navigate } from 'react-router-dom';
import { AnalysisData } from '../api/interfaces';

// Mock данные для графиков (замените на данные из API при наличии)
const historicalData = [
    { year: '2023', current_ratio: 1.2, roe: 0.15, equity_ratio: 0.4 },
    { year: '2024', current_ratio: 1.5, roe: 0.18, equity_ratio: 0.45 },rf
    { year: '2025', current_ratio: 1.8, roe: 0.20, equity_ratio: 0.5 },
];

const comparisonData = [
    { metric: 'Ликвидность', company_value: 1.8, industry_average: 2.0 },
    { metric: 'ROE', company_value: 0.20, industry_average: 0.15 },
    { metric: 'Автономия', company_value: 0.5, industry_average: 0.4 },
];

export const DetailedReport = () => {
    const location = useLocation();
    const result = location.state?.result as AnalysisData | undefined;

    const transactionId = useMemo(() =>
        Math.random().toString(36).substring(2, 11).toUpperCase(),
        []);

    if (!result) {
        return <Navigate to="/" replace />;
    }

    const getRiskColor = (risk: string) => {
        switch (risk) {
            case 'low': return '#00714d';
            case 'medium': return '#f59e0b';
            case 'high': return '#ba1a1a';
            default: return '#6b7280';
        }
    };

    const getRiskBg = (risk: string) => {
        switch (risk) {
            case 'low': return '#6cf8bb';
            case 'medium': return '#fef3c7';
            case 'high': return '#ffdad6';
            default: return '#f3f4f6';
        }
    };

    const handlePrint = () => window.print();

    const metrics = [
        {
            label: 'Ликвидность',
            value: result?.ratios?.current_ratio?.toFixed(2) || '—',
            sub: 'Текущая',
            icon: Activity,
            trend: 'up',
            color: 'teal'
        },
        {
            label: 'Автономия',
            value: result?.ratios?.equity_ratio?.toFixed(2) || '—',
            sub: 'Коэфф. собств. кап.',
            icon: ShieldCheck,
            trend: 'up',
            color: 'blue'
        },
        {
            label: 'ROA',
            value: result?.ratios?.roa ? (result.ratios.roa * 100).toFixed(1) + '%' : '—',
            sub: 'Рент. активов',
            icon: PieChart,
            trend: 'down',
            color: 'indigo'
        },
        {
            label: 'ROE',
            value: result?.ratios?.roe ? (result.ratios.roe * 100).toFixed(1) + '%' : '—',
            sub: 'Рент. капитала',
            icon: TrendingUp,
            trend: 'up',
            color: 'violet'
        },
        {
            label: 'Долг / Выручка',
            value: result?.ratios?.debt_to_revenue?.toFixed(2) || '—',
            sub: 'Долговая нагрузка',
            icon: BarChart3,
            trend: 'down',
            color: 'orange'
        },
        {
            label: 'Маржа',
            value: (result.metrics.revenue && result.metrics.net_profit)
                ? ((result.metrics.net_profit / result.metrics.revenue) * 100).toFixed(1) + '%'
                : '—',
            sub: 'Чистая рентабельность',
            icon: Wallet,
            trend: 'up',
            color: 'cyan'
        },
    ];

    return (
        <Container size="xl" py="2rem">
            <Stack gap="xl">
                {/* HEADER SECTION */}
                <Group justify="space-between" align="center">
                    <Stack gap={4}>
                        <Title order={1} style={{ letterSpacing: '-0.02em', fontWeight: 800 }}>
                            Отчет об анализе: {location.state?.filename || 'Финансовый документ'}
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

                {/* SCORING & AI INSIGHTS */}
                <Card padding="xl" radius="md" shadow="sm" bg="white" style={{ border: 'none' }}>
                    <SimpleGrid cols={{ base: 1, md: 2 }} spacing="2rem">
                        <Stack justify="center" align="center" py="xl">
                            <Text size="sm" fw={700} c="dimmed" tt="uppercase" lts="0.05em">Итоговый скоринг</Text>
                            <Title
                                order={1}
                                style={{
                                    fontSize: '5rem',
                                    fontFamily: 'JetBrains Mono',
                                    color: getRiskColor(result.score.risk_level),
                                    lineHeight: 1
                                }}
                            >
                                {result.score.score}
                            </Title>
                            <Badge
                                size="xl" radius="xl" px="xl"
                                style={{
                                    backgroundColor: getRiskBg(result.score.risk_level),
                                    color: getRiskColor(result.score.risk_level),
                                    border: 'none', fontWeight: 700
                                }}
                            >
                                {result.score.risk_level === 'low' ? 'НИЗКИЙ РИСК' : result.score.risk_level === 'medium' ? 'СРЕДНИЙ РИСК' : 'ВЫСОКИЙ РИСК'}
                            </Badge>
                            <Text c="dimmed" size="sm" ta="center" mt="md" style={{ maxWidth: 300 }}>
                                Компания демонстрирует {result.score.risk_level === 'low' ? 'стабильные' : 'неоднозначные'} показатели финансовой устойчивости.
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

                {/* NEW: VISUALIZATION SECTION */}
                <Card padding="xl" radius="md" shadow="sm" bg="white" style={{ border: 'none' }}>
                    <Title order={3} mb="xl">Динамика показателей</Title>
                    <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="3rem">
                        <Box>
                            <Text fw={700} size="xs" c="dimmed" tt="uppercase" mb="lg">Исторический тренд (3 года)</Text>
                            <LineChart
                                h={300}
                                data={historicalData}
                                dataKey="year"
                                withLegend
                                legendProps={{ verticalAlign: 'bottom', height: 40 }}
                                series={[
                                    { name: 'current_ratio', color: 'blue.6', label: 'Ликвидность' },
                                    { name: 'roe', color: 'teal.6', label: 'ROE' },
                                    { name: 'equity_ratio', color: 'indigo.6', label: 'Автономия' },
                                ]}
                                curveType="monotone"
                                withTooltip
                                gridAxis="xy"
                            />
                        </Box>
                        <Box>
                            <Text fw={700} size="xs" c="dimmed" tt="uppercase" mb="lg">Сравнение с отраслью</Text>
                            <BarChart
                                h={300}
                                data={comparisonData}
                                dataKey="metric"
                                withLegend
                                legendProps={{ verticalAlign: 'bottom', height: 40 }}
                                series={[
                                    { name: 'company_value', color: 'blue.6', label: 'Компания' },
                                    { name: 'industry_average', color: 'gray.4', label: 'Отрасль' },
                                ]}
                                withTooltip
                                gridAxis="y"
                                barProps={{ radius: [4, 4, 0, 0] }}
                            />
                        </Box>
                    </SimpleGrid>
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
                                <Group gap={2} c={m.trend === 'up' ? 'teal' : 'red'}>
                                    {m.trend === 'up' ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                                    <Text size="xs" fw={700}>{m.trend === 'up' ? '+2.4%' : '-1.1%'}</Text>
                                </Group>
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
                                <Table.Th style={{ border: 'none', borderRadius: '0 8px 8px 0' }} align="right">Норматив</Table.Th>
                            </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                            {[
                                { label: 'Выручка (Revenue)', val: result.metrics.revenue, unit: ' ₽' },
                                { label: 'Чистая прибыль (Net Profit)', val: result.metrics.net_profit, unit: ' ₽', bg: '#f8f9fa' },
                                { label: 'Активы (Total Assets)', val: result.metrics.total_assets, unit: ' ₽' },
                                { label: 'Собственный капитал (Equity)', val: result.metrics.equity, unit: ' ₽', bg: '#f8f9fa' }
                            ].map((row, idx) => (
                                <Table.Tr key={idx} style={{ backgroundColor: row.bg || 'transparent' }}>
                                    <Table.Td style={{ border: 'none' }}>{row.label}</Table.Td>
                                    <Table.Td style={{ border: 'none', fontFamily: 'JetBrains Mono' }} align="right">
                                        {row.val?.toLocaleString() || '—'}{row.unit}
                                    </Table.Td>
                                    <Table.Td style={{ border: 'none' }} align="right">—</Table.Td>
                                </Table.Tr>
                            ))}
                        </Table.Tbody>
                    </Table>
                </Card>
            </Stack>
        </Container>
    );
};