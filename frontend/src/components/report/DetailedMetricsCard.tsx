import { Card, Group, Stack, Table, Text } from '@mantine/core';
import { Info } from 'lucide-react';
import { AnalysisData } from '../../api/interfaces';
import ConfidenceBadge from '../ConfidenceBadge';

interface DetailedMetricsCardProps {
    metrics: AnalysisData['metrics'];
    extractionMetadata: AnalysisData['extraction_metadata'];
    reliableCount: number;
}

type MetricRow = {
    label: string;
    metricKey: string;
    value: number | null;
    unit: string;
    bg?: string;
};

const METRIC_ROWS: MetricRow[] = [
    { label: 'Выручка (Revenue)', metricKey: 'revenue', value: null, unit: ' ₽' },
    { label: 'Чистая прибыль (Net Profit)', metricKey: 'net_profit', value: null, unit: ' ₽', bg: '#f8f9fa' },
    { label: 'Активы (Total Assets)', metricKey: 'total_assets', value: null, unit: ' ₽' },
    { label: 'Собственный капитал (Equity)', metricKey: 'equity', value: null, unit: ' ₽', bg: '#f8f9fa' },
];

function buildRows(metrics: AnalysisData['metrics']): MetricRow[] {
    return METRIC_ROWS.map((row) => ({
        ...row,
        value: metrics[row.metricKey as keyof AnalysisData['metrics']] as number | null,
    }));
}

export default function DetailedMetricsCard({
    metrics,
    extractionMetadata,
    reliableCount,
}: DetailedMetricsCardProps) {
    const rows = buildRows(metrics);

    return (
        <Card padding="xl" radius="md" shadow="sm" bg="white" style={{ border: 'none' }}>
            <Text component="h3" size="xl" fw={700} mb="xl">Детализированные показатели</Text>
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
                    {rows.map((row, idx) => {
                        const metadata = extractionMetadata?.[row.metricKey];
                        return (
                            <Table.Tr key={idx} style={{ backgroundColor: row.bg || 'transparent' }}>
                                <Table.Td style={{ border: 'none' }}>{row.label}</Table.Td>
                                <Table.Td style={{ border: 'none', fontFamily: 'JetBrains Mono' }} align="right">
                                    {row.value?.toLocaleString() || '—'}{row.unit}
                                </Table.Td>
                                <Table.Td style={{ border: 'none' }} align="right">
                                    {metadata ? (
                                        <ConfidenceBadge
                                            metricKey={row.metricKey}
                                            confidence={metadata.confidence}
                                            source={metadata.source}
                                            matchSemantics={metadata.match_semantics}
                                            inferenceMode={metadata.inference_mode}
                                            reasonCode={metadata.reason_code}
                                            authoritativeOverride={metadata.authoritative_override}
                                        />
                                    ) : '—'}
                                </Table.Td>
                                <Table.Td style={{ border: 'none' }} align="right">—</Table.Td>
                            </Table.Tr>
                        );
                    })}
                </Table.Tbody>
            </Table>

            {extractionMetadata && (
                <Stack gap="xs" mt="md">
                    <Text size="sm" c="dimmed">
                        Надёжно извлечено: <b>{reliableCount} показателей</b>
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
    );
}
