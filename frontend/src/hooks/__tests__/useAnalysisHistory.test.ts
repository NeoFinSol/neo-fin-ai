import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAnalysisHistory } from '../useAnalysisHistory';
import { AnalysisData } from '../../api/interfaces';

// Helper to create valid AnalysisData mock
const createMockAnalysisData = (scoreValue: number = 75): AnalysisData => ({
    score: {
        score: scoreValue,
        risk_level: scoreValue >= 75 ? 'low' : 'medium',
        confidence_score: 1.0,
        factors: [],
        normalized_scores: {},
    },
    ratios: {
        current_ratio: null,
        quick_ratio: null,
        absolute_liquidity_ratio: null,
        roa: null,
        roe: null,
        ros: null,
        ebitda_margin: null,
        equity_ratio: null,
        financial_leverage: null,
        interest_coverage: null,
        asset_turnover: null,
        inventory_turnover: null,
        receivables_turnover: null,
    },
    metrics: {
        revenue: null,
        net_profit: null,
        total_assets: null,
        equity: null,
        liabilities: null,
        current_assets: null,
        short_term_liabilities: null,
        accounts_receivable: null,
        inventory: null,
        cash_and_equivalents: null,
        ebitda: null,
        ebit: null,
        interest_expense: null,
        cost_of_goods_sold: null,
        average_inventory: null,
    },
    scanned: false,
    text: '',
    tables: [],
    nlp: { risks: [], key_factors: [], recommendations: [] },
    extraction_metadata: {},
});

// Mock localStorage
const localStorageMock = (() => {
    let store: Record<string, string> = {};
    return {
        getItem: vi.fn((key: string) => store[key] || null),
        setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
        removeItem: vi.fn((key: string) => { delete store[key]; }),
        clear: vi.fn(() => { store = {}; }),
    };
})();

Object.defineProperty(window, 'localStorage', {
    value: localStorageMock,
});

// Mock crypto.randomUUID
const mockUuid = 'test-uuid-1234-5678-90ab-cdef';
(vi.spyOn(crypto, 'randomUUID') as any).mockReturnValue(mockUuid);

describe('useAnalysisHistory', () => {
    beforeEach(() => {
        localStorageMock.clear();
        vi.clearAllMocks();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('initializes with empty history when localStorage is empty', () => {
        const { result } = renderHook(() => useAnalysisHistory());
        
        expect(result.current.history).toEqual([]);
        expect(localStorageMock.getItem).toHaveBeenCalledWith('neofin_analysis_history');
    });

    it('loads history from localStorage on mount', () => {
        const mockHistory = [
            {
                id: 'existing-id',
                filename: 'test.pdf',
                date: '25.03.2026',
                score: 75,
                riskLevel: 'low',
                result: createMockAnalysisData(75),
            },
        ];
        
        localStorageMock.getItem.mockReturnValue(JSON.stringify(mockHistory));
        
        const { result } = renderHook(() => useAnalysisHistory());
        
        expect(result.current.history).toEqual(mockHistory);
    });

    it('handles invalid JSON in localStorage gracefully', () => {
        localStorageMock.getItem.mockReturnValue('invalid json');
        
        const { result } = renderHook(() => useAnalysisHistory());
        
        expect(result.current.history).toEqual([]);
    });

    it('adds new entry to history', () => {
        const { result } = renderHook(() => useAnalysisHistory());
        
        const mockResult = createMockAnalysisData(85);
        
        act(() => {
            result.current.addEntry('report.pdf', mockResult);
        });
        
        expect(result.current.history).toHaveLength(1);
        expect(result.current.history[0].filename).toBe('report.pdf');
        expect(result.current.history[0].score).toBe(85);
        expect(result.current.history[0].riskLevel).toBe('low');
        expect(result.current.history[0].id).toBeDefined();
    });

    it('removes entry from history by id', () => {
        const mockHistory = [
            { id: '1', filename: 'first.pdf', date: '25.03.2026', score: 70, riskLevel: 'medium', result: createMockAnalysisData(70) },
            { id: '2', filename: 'second.pdf', date: '25.03.2026', score: 80, riskLevel: 'low', result: createMockAnalysisData(80) },
        ];
        localStorageMock.getItem.mockReturnValue(JSON.stringify(mockHistory));
        
        const { result } = renderHook(() => useAnalysisHistory());
        
        act(() => {
            result.current.removeEntry('1');
        });
        
        expect(result.current.history).toHaveLength(1);
        expect(result.current.history[0].id).toBe('2');
    });

    it('clears entire history', () => {
        const mockHistory = [
            { id: '1', filename: 'test.pdf', date: '25.03.2026', score: 70, riskLevel: 'medium', result: createMockAnalysisData(70) },
        ];
        localStorageMock.getItem.mockReturnValue(JSON.stringify(mockHistory));
        
        const { result } = renderHook(() => useAnalysisHistory());
        
        expect(result.current.history).toHaveLength(1);
        
        act(() => {
            result.current.clearHistory();
        });
        
        expect(result.current.history).toHaveLength(0);
    });

    it('gets entry by id', () => {
        const mockHistory = [
            { id: 'unique-id', filename: 'test.pdf', date: '25.03.2026', score: 70, riskLevel: 'medium', result: createMockAnalysisData(70) },
        ];
        localStorageMock.getItem.mockReturnValue(JSON.stringify(mockHistory));
        
        const { result } = renderHook(() => useAnalysisHistory());
        
        const entry = result.current.getEntry('unique-id');
        
        expect(entry).toBeDefined();
        expect(entry?.filename).toBe('test.pdf');
    });

    it('returns undefined for non-existent entry id', () => {
        const mockHistory = [
            { id: 'existing-id', filename: 'test.pdf', date: '25.03.2026', score: 70, riskLevel: 'medium', result: createMockAnalysisData(70) },
        ];
        localStorageMock.getItem.mockReturnValue(JSON.stringify(mockHistory));
        
        const { result } = renderHook(() => useAnalysisHistory());
        
        const entry = result.current.getEntry('non-existent-id');
        
        expect(entry).toBeUndefined();
    });

    it('persists history to localStorage on change', () => {
        const { result } = renderHook(() => useAnalysisHistory());
        
        const mockResult = createMockAnalysisData(90);
        
        act(() => {
            result.current.addEntry('test.pdf', mockResult);
        });
        
        expect(localStorageMock.setItem).toHaveBeenCalledWith(
            'neofin_analysis_history',
            expect.any(String)
        );
    });

    it('maintains chronological order (newest first)', () => {
        const { result } = renderHook(() => useAnalysisHistory());
        
        const mockResult1 = createMockAnalysisData(70);
        const mockResult2 = createMockAnalysisData(80);
        
        act(() => {
            result.current.addEntry('first.pdf', mockResult1);
            result.current.addEntry('second.pdf', mockResult2);
        });
        
        expect(result.current.history[0].filename).toBe('second.pdf');
        expect(result.current.history[1].filename).toBe('first.pdf');
    });

    it('handles missing score in result gracefully', () => {
        const { result } = renderHook(() => useAnalysisHistory());
        
        const mockResult = {
            ...createMockAnalysisData(),
            score: undefined,
        } as AnalysisData;
        
        act(() => {
            result.current.addEntry('test.pdf', mockResult);
        });
        
        expect(result.current.history[0].score).toBe(0);
        expect(result.current.history[0].riskLevel).toBe('medium');
    });
});
