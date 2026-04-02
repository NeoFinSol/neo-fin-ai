import {
    Accordion,
    Badge,
    Card,
    Divider,
    Group,
    SimpleGrid,
    Stack,
    Text,
    ThemeIcon,
    Title,
    Tooltip,
} from '@mantine/core';
import {
    Activity,
    Minus,
    TrendingDown,
    TrendingUp,
} from 'lucide-react';

import { AIRuntimeInfo, FinancialRatios, NLPResult, ScoreData, ScoringMethodology } from '../../api/interfaces';

interface ScoreInsightsCardProps {
    score: ScoreData;
    nlp?: NLPResult;
    aiRuntime?: AIRuntimeInfo;
    ratios?: FinancialRatios;
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

function hasNlpContent(nlp?: NLPResult): boolean {
    if (!nlp) {
        return false;
    }
    return [nlp.risks, nlp.key_factors].some((items) => Array.isArray(items) && items.length > 0);
}

function getBenchmarkBadge(methodology?: ScoringMethodology): string | null {
    if (!methodology) {
        return null;
    }
    return methodology.benchmark_profile === 'retail_demo' ? 'Ритейл-бенчмарк' : 'Общий бенчмарк';
}

function getPeriodBadge(methodology?: ScoringMethodology): string | null {
    if (!methodology) {
        return null;
    }
    if (methodology.period_basis === 'annualized_q1') {
        return 'Годовая база Q1';
    }
    if (methodology.period_basis === 'annualized_h1') {
        return 'Годовая база H1';
    }
    return null;
}

function getGuardrailBadge(methodology?: ScoringMethodology): string | null {
    if (!methodology?.guardrails?.length) {
        return null;
    }
    return 'Ограничение данных';
}

function describeGuardrails(methodology?: ScoringMethodology): string | null {
    if (!methodology?.guardrails?.length) {
        return null;
    }

    const labels = methodology.guardrails.map((item) => {
        if (item === 'low_confidence') {
            return 'низкая полнота коэффициентов';
        }
        if (item.startsWith('missing_core:')) {
            return `нет ключевого показателя ${item.split(':')[1]}`;
        }
        if (item.startsWith('missing_supporting:')) {
            return `не хватает поддерживающего показателя ${item.split(':')[1]}`;
        }
        return item;
    });

    return `Ограничение достоверности: ${labels.join(', ')}.`;
}

function buildMethodologySummary(methodology?: ScoringMethodology): string | null {
    if (!methodology) {
        return null;
    }

    const benchmark = methodology.benchmark_profile === 'retail_demo'
        ? 'ритейл-бенчмарку'
        : 'общему бенчмарку';
    const period = methodology.period_basis === 'annualized_q1'
        ? 'с годовой базой Q1'
        : methodology.period_basis === 'annualized_h1'
            ? 'с годовой базой H1'
            : 'по отчётному периоду';

    return `Скоринг рассчитан по ${benchmark} ${period}.`;
}

function getLeverageBasisLabel(methodology?: ScoringMethodology): string | null {
    if (!methodology) {
        return null;
    }
    return methodology.leverage_basis === 'debt_only'
        ? 'Рычаг по долгам'
        : 'Рычаг по обязательствам';
}

function formatRatioValue(value?: number | null): string {
    if (value == null) {
        return '—';
    }
    return value.toFixed(2);
}

function describeAiState(aiRuntime?: AIRuntimeInfo): string {
    if (!aiRuntime) {
        return 'Карточка ниже построена на детерминированном скоринге и рассчитанных финансовых коэффициентах. Для этого отчёта не зафиксирован отдельный AI-статус, поэтому выводы показаны только по извлечённым метрикам и score-факторам.';
    }

    const providerName = aiRuntime.effective_provider ?? aiRuntime.requested_provider;

    if (aiRuntime.status === 'skipped') {
        return 'AI-контур не использовался в этой задаче. Ниже показана детерминированная аналитика по извлечённым метрикам и score-факторам.';
    }

    if (aiRuntime.status === 'empty') {
        return `Модель была вызвана, но не вернула содержательные пояснения для аналитического блока (${providerName}). Ниже показана детерминированная аналитика по извлечённым метрикам и score-факторам.`;
    }

    if (aiRuntime.status === 'failed') {
        return `AI-контур ${providerName} завершился с ошибкой, поэтому ниже показана детерминированная аналитика по извлечённым метрикам и score-факторам.`;
    }

    return 'AI-контур отработал успешно.';
}

export default function ScoreInsightsCard({ score, nlp, aiRuntime, ratios }: ScoreInsightsCardProps) {
    const showAiInsights = aiRuntime?.status === 'succeeded' && hasNlpContent(nlp);
    const benchmarkBadge = getBenchmarkBadge(score.methodology);
    const periodBadge = getPeriodBadge(score.methodology);
    const guardrailBadge = getGuardrailBadge(score.methodology);
    const methodologySummary = buildMethodologySummary(score.methodology);
    const guardrailSummary = describeGuardrails(score.methodology);
    const leverageBasisLabel = getLeverageBasisLabel(score.methodology);
    const methodologyAdjustments = score.methodology?.adjustments ?? [];
    const issuerOverrideCodes = methodologyAdjustments.filter((item) => item.startsWith('issuer_override:'));
    const positiveFactors = score.factors
        .filter((factor) => factor.impact === 'positive')
        .map((factor) => factor.name)
        .join(', ') || 'Стабильность базовых метрик';
    const negativeFactors = score.factors
        .filter((factor) => factor.impact === 'negative')
        .map((factor) => factor.name)
        .join(', ') || 'Существенных рисков не обнаружено';
    const keyFactors = nlp?.key_factors?.join(', ') || 'Ключевые факторы не выделены';
    const risks = nlp?.risks?.join(', ') || 'Явные риски не выделены';

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
                    {(benchmarkBadge || periodBadge || guardrailBadge) && (
                        <Stack gap={6} align="center">
                            <Group gap="xs" justify="center">
                                {benchmarkBadge && (
                                    <Badge variant="light" color="blue" radius="xl">
                                        {benchmarkBadge}
                                    </Badge>
                                )}
                                {periodBadge && (
                                    <Badge variant="light" color="violet" radius="xl">
                                        {periodBadge}
                                    </Badge>
                                )}
                                {guardrailBadge && (
                                    <Badge variant="light" color="orange" radius="xl">
                                        {guardrailBadge}
                                    </Badge>
                                )}
                            </Group>
                            {methodologySummary && (
                                <Text c="dimmed" size="xs" ta="center" style={{ maxWidth: 320 }}>
                                    {methodologySummary}
                                </Text>
                            )}
                            {guardrailSummary && (
                                <Text c="orange.8" size="xs" ta="center" style={{ maxWidth: 320 }}>
                                    {guardrailSummary}
                                </Text>
                            )}
                        </Stack>
                    )}
                    {score.methodology && (
                        <Accordion
                            variant="separated"
                            radius="md"
                            w="100%"
                            maw={420}
                            mt="md"
                        >
                            <Accordion.Item value="methodology">
                                <Accordion.Control>Как рассчитано</Accordion.Control>
                                <Accordion.Panel>
                                    <Stack gap="xs">
                                        {leverageBasisLabel && (
                                            <Text size="sm">
                                                {leverageBasisLabel}: активный коэффициент финансового рычага использует{' '}
                                                {score.methodology.leverage_basis === 'debt_only'
                                                    ? 'процентный долг / капитал'
                                                    : 'все обязательства / капитал'}.
                                            </Text>
                                        )}
                                        {ratios && (
                                            <Stack gap={2}>
                                                <Text size="sm">
                                                    Фин. рычаг (alias): {formatRatioValue(ratios.financial_leverage)}
                                                </Text>
                                                <Text size="sm">
                                                    Фин. рычаг total: {formatRatioValue(ratios.financial_leverage_total)}
                                                </Text>
                                                <Text size="sm">
                                                    Фин. рычаг debt-only: {formatRatioValue(ratios.financial_leverage_debt_only)}
                                                </Text>
                                            </Stack>
                                        )}
                                        {methodologyAdjustments.includes('interest_coverage_sign_corrected') && (
                                            <Text size="sm">
                                                Корректировка знака процентов: показатель покрытия процентов считается
                                                через `EBIT / abs(interest_expense)`, если финансовые расходы в
                                                отчёте отражены отрицательным числом.
                                            </Text>
                                        )}
                                        {score.methodology.ifrs16_adjusted && (
                                            <Text size="sm">
                                                Корректировка IFRS 16 включена для интерпретации lease-heavy retail.
                                            </Text>
                                        )}
                                        {issuerOverrideCodes.map((code) => (
                                            <Text key={code} size="sm">
                                                {code}: для Magnit H1 2025 применён зафиксированный в репозитории
                                                issuer fallback по официальному источнику эмитента.
                                            </Text>
                                        ))}
                                        {score.methodology.peer_context.map((note) => (
                                            <Text key={note} size="sm">
                                                {note}
                                            </Text>
                                        ))}
                                    </Stack>
                                </Accordion.Panel>
                            </Accordion.Item>
                        </Accordion>
                    )}
                    <Text c="dimmed" size="sm" ta="center" mt="md" style={{ maxWidth: 300 }}>
                        Компания демонстрирует {getRiskNarrative(score.risk_level)} показатели финансовой устойчивости.
                    </Text>
                </Stack>

                <Stack gap="md">
                    <Group gap="xs">
                        <ThemeIcon variant="light" color="blue" radius="xl">
                            <Activity size={16} />
                        </ThemeIcon>
                        <Title order={3}>
                            {showAiInsights ? 'AI-Инсайты и Аналитика' : 'Скоринговая аналитика'}
                        </Title>
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
                        {showAiInsights ? (
                            <>
                                Модель выделила ключевые факторы из текстовой части отчёта и сопоставила их
                                с рассчитанными метриками.
                                <br /><br />
                                <b>Ключевые факторы:</b> {keyFactors}.
                                <br />
                                <b>Риски:</b> {risks}.
                            </>
                        ) : (
                            <>
                                {describeAiState(aiRuntime)}
                                <br /><br />
                                <b>Сильные стороны:</b> {positiveFactors}.
                                <br />
                                <b>Области внимания:</b> {negativeFactors}.
                            </>
                        )}
                    </Text>

                    <Stack gap="sm" mt="md">
                        <Text fw={700} size="sm" tt="uppercase" c="dimmed" lts="0.05em">Факторы скоринга</Text>
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
