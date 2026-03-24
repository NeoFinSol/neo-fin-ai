/**
 * Unit tests for AnalysisHistory component
 * Feature: analysis-history-visualization
 * Requirements: 3.1, 3.2, 3.3, 3.4, 3.7
 */
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { MantineProvider } from '@mantine/core';

// ---------------------------------------------------------------------------
// Mock apiClient before importing the component
// ---------------------------------------------------------------------------
vi.mock('../../api/client', () => ({
    apiClient: {
        get: vi.fn(),
    },
}));

// Mock DetailedReport to avoid rendering its full tree in unit tests
vi.mock('../DetailedReport', () => ({
    DetailedReport: ({ filename }: { filename?: string }) => (
        <div data-testid="detailed-report">{filename}</div>
    ),
}));

import { AnalysisHistory } from '../AnalysisHistory';
import { apiClient } from '../../api/client';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockGet = apiClient.get as ReturnType<typeof vi.fn>;

function makeListResponse(overrides: Partial<{
    items: any[];
    total: number;
    page: number;
    page_size: number;
}> = {}) {
    return {
        data: {
            items: [],
            total: 0,
            page: 1,
            page_size: 20,
            ...overrides,
        },
    };
}

function makeSummary(overrides: Partial<{
    task_id: string;
    status: string;
    created_at: string;
    score: number | null;
    risk_level: string | null;
    filename: string | null;
}> = {}) {
    return {
        task_id: 'task-001',
        status: 'completed',
        created_at: '2024-06-15T10:00:00Z',
        score: 72.5,
        risk_level: 'medium',
        filename: 'report.pdf',
        ...overrides,
    };
}

function renderComponent() {
    return render(
        <MantineProvider>
            <AnalysisHistory />
        </MantineProvider>
    );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AnalysisHistory', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    // -------------------------------------------------------------------------
    // Requirement 3.1 — calls GET /analyses on mount
    // -------------------------------------------------------------------------
    it('calls GET /analyses on mount', async () => {
        mockGet.mockResolvedValueOnce(makeListResponse());

        renderComponent();

        await waitFor(() => {
            expect(mockGet).toHaveBeenCalledTimes(1);
            expect(mockGet).toHaveBeenCalledWith('/analyses?page=1&page_size=20');
        });
    });

    // -------------------------------------------------------------------------
    // Requirement 3.2 — shows Skeleton while loading
    // -------------------------------------------------------------------------
    it('shows skeleton while loading', async () => {
        // Never resolves — keeps loading state active throughout the test
        mockGet.mockReturnValueOnce(new Promise(() => { }));

        const { container } = renderComponent();

        // Mantine Skeleton renders divs with data-skeleton attribute
        await waitFor(() => {
            const skeletons = container.querySelectorAll('.mantine-Skeleton-root');
            expect(skeletons.length).toBeGreaterThan(0);
        });
    });

    // -------------------------------------------------------------------------
    // Requirement 3.3 — shows error alert + retry button on API failure
    // -------------------------------------------------------------------------
    it('shows error message and retry button when API fails', async () => {
        mockGet.mockRejectedValueOnce({
            message: 'Network Error',
            response: undefined,
        });

        renderComponent();

        await waitFor(() => {
            expect(screen.getByRole('alert')).toBeInTheDocument();
        });

        expect(screen.getByText('Повторить')).toBeInTheDocument();
    });

    it('retries the request when retry button is clicked', async () => {
        mockGet
            .mockRejectedValueOnce({ message: 'Network Error' })
            .mockResolvedValueOnce(makeListResponse());

        renderComponent();

        await waitFor(() => screen.getByText('Повторить'));

        await act(async () => {
            await userEvent.click(screen.getByText('Повторить'));
        });

        await waitFor(() => {
            expect(mockGet).toHaveBeenCalledTimes(2);
        });
    });

    // -------------------------------------------------------------------------
    // Requirement 3.4 — shows Pagination when total > page_size
    // -------------------------------------------------------------------------
    it('shows pagination when total exceeds page_size', async () => {
        const items = Array.from({ length: 20 }, (_, i) =>
            makeSummary({ task_id: `task-${i}`, filename: `file-${i}.pdf` })
        );
        mockGet.mockResolvedValueOnce(makeListResponse({ items, total: 45, page: 1, page_size: 20 }));

        renderComponent();

        // Wait for data to load, then check pagination is present.
        // Mantine Pagination renders a group of buttons — check for page "2" button.
        await waitFor(() => {
            expect(screen.getByRole('button', { name: '2' })).toBeInTheDocument();
        });
    });

    it('does NOT show pagination when total <= page_size', async () => {
        const items = [makeSummary()];
        mockGet.mockResolvedValueOnce(makeListResponse({ items, total: 1, page: 1, page_size: 20 }));

        renderComponent();

        await waitFor(() => screen.getByText('report.pdf'));

        // No page "2" button should exist
        expect(screen.queryByRole('button', { name: '2' })).not.toBeInTheDocument();
    });

    // -------------------------------------------------------------------------
    // Requirement 3.7 — displays "—" for null score and risk_level
    // -------------------------------------------------------------------------
    it('displays "—" for null score', async () => {
        const items = [makeSummary({ score: null, risk_level: 'low', filename: 'test.pdf' })];
        mockGet.mockResolvedValueOnce(makeListResponse({ items, total: 1 }));

        renderComponent();

        await waitFor(() => screen.getByText('test.pdf'));

        const dashes = screen.getAllByText('—');
        expect(dashes.length).toBeGreaterThanOrEqual(1);
    });

    it('displays "—" for null risk_level', async () => {
        const items = [makeSummary({ score: 55.0, risk_level: null, filename: 'test2.pdf' })];
        mockGet.mockResolvedValueOnce(makeListResponse({ items, total: 1 }));

        renderComponent();

        await waitFor(() => screen.getByText('test2.pdf'));

        const dashes = screen.getAllByText('—');
        expect(dashes.length).toBeGreaterThanOrEqual(1);
    });

    it('displays "—" for both null score and null risk_level', async () => {
        const items = [makeSummary({ score: null, risk_level: null, filename: 'nulls.pdf' })];
        mockGet.mockResolvedValueOnce(makeListResponse({ items, total: 1 }));

        renderComponent();

        await waitFor(() => screen.getByText('nulls.pdf'));

        const dashes = screen.getAllByText('—');
        expect(dashes.length).toBeGreaterThanOrEqual(2);
    });

    // -------------------------------------------------------------------------
    // Bonus: formats date as DD.MM.YYYY
    // -------------------------------------------------------------------------
    it('formats created_at as DD.MM.YYYY', async () => {
        const items = [makeSummary({ created_at: '2024-06-15T10:00:00Z' })];
        mockGet.mockResolvedValueOnce(makeListResponse({ items, total: 1 }));

        renderComponent();

        await waitFor(() => screen.getByText('15.06.2024'));
    });
});

// ---------------------------------------------------------------------------
// Property 10: Round-trip форматирования даты
// Feature: analysis-history-visualization, Property 10: round-trip форматирования даты
// Validates: Requirements 3.6, 6.5
// ---------------------------------------------------------------------------
import * as fc from 'fast-check';
import { formatDate } from '../AnalysisHistory';

describe('formatDate — property-based tests', () => {
    // Arbitrary: случайная дата в диапазоне 1970–2099, сериализованная в ISO 8601
    const isoDateArbitrary = fc
        .date({ min: new Date('1970-01-01T00:00:00Z'), max: new Date('2099-12-31T23:59:59Z') })
        .map((d) => d.toISOString());

    it('Property 10: round-trip — DD.MM.YYYY совпадает с исходной датой (100 итераций)', () => {
        fc.assert(
            fc.property(isoDateArbitrary, (isoDate) => {
                const formatted = formatDate(isoDate);

                // Формат строго DD.MM.YYYY
                expect(formatted).toMatch(/^\d{2}\.\d{2}\.\d{4}$/);

                const [dayStr, monthStr, yearStr] = formatted.split('.');
                const original = new Date(isoDate);

                // День, месяц, год совпадают с исходной датой (UTC)
                expect(parseInt(dayStr)).toBe(original.getUTCDate());
                expect(parseInt(monthStr)).toBe(original.getUTCMonth() + 1);
                expect(parseInt(yearStr)).toBe(original.getUTCFullYear());
            }),
            { numRuns: 100 },
        );
    });
});
