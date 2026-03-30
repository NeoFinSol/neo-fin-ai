import {
    Card,
    Divider,
    Group,
    SimpleGrid,
    Stack,
    Text,
    ThemeIcon,
    Title,
    Tooltip,
    Badge,
} from '@mantine/core';
import {
    Activity,
    TrendingDown,
    TrendingUp,
    Minus,
} from 'lucide-react';

import { ScoreData } from '../../api/interfaces';

interface ScoreInsightsCardProps {
    score: ScoreData;
}

function getRiskColor(risk: string): string {
    switch (risk) {
        case 'low':
            return '#00714d';
        case 'medium':
            return '#f59e0b';
        case 'high':
            return '#ba1a1a';
        case 'critical':
            return '#8b0000';
        default:
            return '#6b7280';
    }
}

function getRiskBg(risk: string): string {
    switch (risk) {
        case 'low':
            return '#6cf8bb';
        case 'medium':
            return '#fef3c7';
        case 'high':
            return '#ffdad6';
        case 'critical':
            return '#ffd7d7';
        default:
            return '#f3f4f6';
    }
}

function getRiskLabel(risk: string): string {
    switch (risk) {
        case 'low':
            return 'НИЗКИЙ РИСК';
        case 'medium':
            return 'СРЕДНИЙ РИСК';
        case 'high':
            return 'ВЫСОКИЙ РИСК';
        default:
            return 'КРИТИЧЕСКИЙ РИСК';
    }
}

function getRiskNarrative(risk: string): string {
    if (risk === 'low') {
        return 'стабильные';
    }
    return 'требующие внимания';
}

export default function ScoreInsightsCard({ score }: ScoreInsightsCardProps) {
    return (
        <Card padding="xl" radius="md" shadow="sm" bg="white" style={{ border: 'none' }}>
            <SimpleGrid cols={{ base: 1, md: 2 }} spacing="2rem">
                <Stack justify="center" align="center" py="xl">
                    <Text size="sm" fw={700} c="dimmed" tt="uppercase" lts="0.05em">
                        Итоговый скоринг
                    </Text>
                    <Tooltip
                        label={`Достоверность данных: ${(score.confidence_score * 100).toFixed(0)}%. Рассчитано на основе весов доступных коэффициентов.`}
                        withArrow
                        position="top"
                    >
                        <Title
                            order={1}
                            style={{
                                fontSize: '5rem',
                                fontFamily: 'JetBrains Mono',
                                color: getRiskColor(score.risk_level),
                                lineHeight: 1,
                                cursor: 'help',
                            }}
                        >
                            {score.score}
                        </Title>
                    </Tooltip>
                    <Badge
                        size="xl"
                        radius="xl"
                        px="xl"
                        style={{
                            backgroundColor: getRiskBg(score.risk_level),
                            color: getRiskColor(score.risk_level),
                            border: 'none',
                            fontWeight: 700,
                        }}
                    >
                        {getRiskLabel(score.risk_level)}
                    </Badge>
                    <Text c="dimmed" size="sm" ta="center" mt="md" style={{ maxWidth: 300 }}>
                        Компания демонстрирует {getRiskNarrative(score.risk_level)} показатели финансовой устойчивости.
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
                            letterSpacing: '-0.01em',
                        }}
                    >
                        На основе глубокого анализа предоставленной финансовой отчетности, наша модель искусственного
                        интеллекта выявила ключевые паттерны в структуре капитала.
                        <br /><br />
                        <b>Сильные стороны:</b>{' '}
                        {score.factors.filter((factor) => factor.impact === 'positive').map((factor) => factor.name).join(', ')
                            || 'Стабильность базовых метрик'}.
                        <br />
                        <b>Области внимания:</b>{' '}
                        {score.factors.filter((factor) => factor.impact === 'negative').map((factor) => factor.name).join(', ')
                            || 'Существенных рисков не обнаружено'}.
                    </Text>

                    <Stack gap="sm" mt="md">
                        <Text fw={700} size="sm" tt="uppercase" c="dimmed" lts="0.05em">Факторы риска</Text>
                        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xs">
                            {score.factors.map((factor, idx) => {
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
                                                <Text size="xs" c="dimmed" style={{ lineHeight: 1.4 }}>
                                                    {factor.description}
                                                </Text>
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
    );
}
