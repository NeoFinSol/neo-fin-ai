import { describe, expect, it } from 'vitest';
import { AnalysisData } from '../../api/interfaces';
import { countReliableMetrics } from '../reliability';

describe('countReliableMetrics', () => {
    it('returns zero when metadata is missing', () => {
        expect(countReliableMetrics(undefined)).toBe(0);
    });

    it('counts metrics with confidence above or equal to threshold', () => {
        const metadata: AnalysisData['extraction_metadata'] = {
            revenue: { confidence: 0.9, source: 'table_exact' },
            net_profit: { confidence: 0.5, source: 'text_regex' },
            equity: { confidence: 0.49, source: 'derived' },
        };

        expect(countReliableMetrics(metadata)).toBe(2);
    });

    it('supports custom threshold', () => {
        const metadata: AnalysisData['extraction_metadata'] = {
            revenue: { confidence: 0.9, source: 'table_exact' },
            net_profit: { confidence: 0.6, source: 'text_regex' },
            equity: { confidence: 0.59, source: 'derived' },
        };

        expect(countReliableMetrics(metadata, 0.6)).toBe(2);
    });
});
