import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MantineProvider } from '@mantine/core';

import { Dashboard } from '../Dashboard';

const mockApiGet = vi.fn();
const mockAnalyze = vi.fn();
const mockReset = vi.fn();
const mockAddEntry = vi.fn();

vi.mock('../../api/client', () => ({
    apiClient: {
        get: (...args: unknown[]) => mockApiGet(...args),
    },
}));

vi.mock('../../context/AnalysisContext', () => ({
    useAnalysis: () => ({
        status: 'idle',
        result: null,
        filename: '',
        error: null,
        analyze: mockAnalyze,
        reset: mockReset,
    }),
}));

vi.mock('../../context/AnalysisHistoryContext', () => ({
    useHistory: () => ({
        addEntry: mockAddEntry,
    }),
}));

describe('Dashboard', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockApiGet.mockResolvedValue({
            data: {
                default_provider: 'gigachat',
                available_providers: ['auto', 'ollama', 'gigachat'],
            },
        });
    });

    it('renders localized hero and prefers ollama when it is available', async () => {
        render(
            <MantineProvider>
                <Dashboard />
            </MantineProvider>,
        );

        expect(screen.getByRole('heading', { name: 'НеоФин.Документы' })).toBeInTheDocument();
        expect(screen.getAllByText(/первый модуль экосистемы неофин\.контур/i).length).toBeGreaterThan(0);
        expect(screen.getByText('Загрузка отчёта')).toBeInTheDocument();

        await waitFor(() => {
            expect(mockApiGet).toHaveBeenCalledWith('/system/ai/providers');
        });

        await waitFor(() => {
            expect(screen.getByText(/Провайдер: Ollama/i)).toBeInTheDocument();
        });
        expect(screen.getByLabelText('Авто')).toBeInTheDocument();
        expect(screen.getByLabelText('Ollama')).toBeInTheDocument();
        expect(screen.getByText(/Переключатель влияет на AI-контур анализа/i)).toBeInTheDocument();
        expect(screen.getByText(/помогает предпринимателям анализировать финансовые документы/i)).toBeInTheDocument();
    });
});
