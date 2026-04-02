import { describe, it, expect } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MantineProvider } from '@mantine/core';

import ScoreInsightsCard from '../report/ScoreInsightsCard';
import { AIRuntimeInfo, NLPResult, ScoreData } from '../../api/interfaces';

const wrapper = ({ children }: { children: React.ReactNode }) => (
    <MantineProvider>{children}</MantineProvider>
);

const baseScore: ScoreData = {
    score: 23.82,
    risk_level: 'critical',
    confidence_score: 0.95,
    methodology: {
        benchmark_profile: 'retail_demo',
        period_basis: 'annualized_h1',
        detection_mode: 'auto',
        reasons: ['retail_keyword', 'period_marker:h1'],
        guardrails: ['missing_core:revenue'],
        leverage_basis: 'debt_only',
        ifrs16_adjusted: true,
        adjustments: [
            'interest_coverage_sign_corrected',
            'leverage_debt_only',
            'issuer_override:ebitda',
        ],
        peer_context: [
            'Large food retail may operate with current ratio below 1; Walmart current ratio ~0.79 (Jan 2026 reference).',
        ],
    },
    factors: [
        {
            name: 'Финансовый рычаг',
            description: 'Значение 8.47 — выше нормы',
            impact: 'negative',
        },
        {
            name: 'Оборачиваемость ДЗ',
            description: 'Значение 83.41 — в норме',
            impact: 'positive',
        },
    ],
    normalized_scores: {
        financial_leverage: 0,
        receivables_turnover: 1,
    },
};

const succeededRuntime: AIRuntimeInfo = {
    requested_provider: 'ollama',
    effective_provider: 'ollama',
    status: 'succeeded',
    reason_code: null,
};

describe('ScoreInsightsCard', () => {
    it('shows deterministic copy when AI was skipped', () => {
        render(
            <ScoreInsightsCard
                score={baseScore}
                aiRuntime={{
                    requested_provider: 'ollama',
                    effective_provider: null,
                    status: 'skipped',
                    reason_code: 'provider_unavailable',
                }}
            />,
            { wrapper },
        );

        expect(screen.getByText('Скоринговая аналитика')).toBeInTheDocument();
        expect(screen.queryByText('AI-Инсайты и Аналитика')).not.toBeInTheDocument();
        expect(screen.getByText(/AI-контур не использовался в этой задаче/i)).toBeInTheDocument();
    });

    it('renders AI insights only when NLP data is present', () => {
        const nlp: NLPResult = {
            risks: ['Высокая долговая нагрузка'],
            key_factors: ['Снижение чистой прибыли'],
            recommendations: ['Сократить долговую нагрузку'],
        };

        render(<ScoreInsightsCard score={baseScore} nlp={nlp} aiRuntime={succeededRuntime} />, { wrapper });

        expect(screen.getByText('AI-Инсайты и Аналитика')).toBeInTheDocument();
        expect(screen.getByText(/Снижение чистой прибыли/i)).toBeInTheDocument();
        expect(screen.getByText(/Высокая долговая нагрузка/i)).toBeInTheDocument();
        expect(screen.queryByText(/AI-анализ сейчас недоступен/i)).not.toBeInTheDocument();
    });

    it('does not switch to AI mode when model returned no narrative content', () => {
        const nlp: NLPResult = {
            risks: [],
            key_factors: [],
            recommendations: [
                'Анализ данных компании завершён. Рекомендуется тщательно изучить предоставленные метрики и факторы риска.',
            ],
        };

        render(
            <ScoreInsightsCard
                score={baseScore}
                nlp={nlp}
                aiRuntime={{
                    requested_provider: 'ollama',
                    effective_provider: 'ollama',
                    status: 'empty',
                    reason_code: 'no_nlp_content',
                }}
            />,
            { wrapper },
        );

        expect(screen.getByText('Скоринговая аналитика')).toBeInTheDocument();
        expect(screen.queryByText('AI-Инсайты и Аналитика')).not.toBeInTheDocument();
        expect(screen.getByText(/Модель была вызвана, но не вернула содержательные пояснения/i)).toBeInTheDocument();
    });

    it('shows provider-specific failure copy when AI failed', () => {
        render(
            <ScoreInsightsCard
                score={baseScore}
                aiRuntime={{
                    requested_provider: 'ollama',
                    effective_provider: 'ollama',
                    status: 'failed',
                    reason_code: 'provider_error',
                }}
            />,
            { wrapper },
        );

        expect(screen.getByText(/AI-контур Ollama завершился с ошибкой/i)).toBeInTheDocument();
    });

    it('renders scoring methodology badges and guardrail note', () => {
        render(<ScoreInsightsCard score={baseScore} aiRuntime={succeededRuntime} />, { wrapper });

        expect(screen.getAllByText(/Ритейл-бенчмарк/i).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/Годовая база H1/i).length).toBeGreaterThan(0);
        expect(screen.getByText(/Ограничение данных/i)).toBeInTheDocument();
        expect(screen.getByText(/скоринг рассчитан по ритейл-бенчмарку/i)).toBeInTheDocument();
    });

    it('renders explainability details in the methodology accordion', () => {
        render(<ScoreInsightsCard score={baseScore} aiRuntime={succeededRuntime} />, { wrapper });

        fireEvent.click(screen.getByRole('button', { name: /как рассчитано/i }));

        expect(screen.getByText(/Рычаг по долгам/i)).toBeInTheDocument();
        expect(screen.getByText(/Корректировка IFRS 16 включена/i)).toBeInTheDocument();
        expect(screen.getByText(/Корректировка знака процентов/i)).toBeInTheDocument();
        expect(screen.getByText(/issuer_override:ebitda/i)).toBeInTheDocument();
        expect(screen.getByText(/Walmart current ratio ~0\.79/i)).toBeInTheDocument();
    });
});
