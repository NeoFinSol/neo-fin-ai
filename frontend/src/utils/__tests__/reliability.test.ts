import { describe, expect, it } from 'vitest';
import { AnalysisData } from '../../api/interfaces';
import { countReliableMetrics, survivesConfidenceFilter } from '../reliability';

describe('countReliableMetrics', () => {
    it('returns zero when metadata is missing', () => {
        expect(countReliableMetrics(undefined)).toBe(0);
    });

    it('counts metrics with confidence above or equal to threshold', () => {
        const metadata: AnalysisData['extraction_metadata'] = {
            revenue: { confidence: 0.9, source: 'table', match_semantics: 'exact', inference_mode: 'direct' },
            net_profit: { confidence: 0.5, source: 'text', match_semantics: 'keyword_match', inference_mode: 'direct' },
            equity: { confidence: 0.49, source: 'derived' },
        };

        expect(countReliableMetrics(metadata)).toBe(2);
    });

    it('supports custom threshold', () => {
        const metadata: AnalysisData['extraction_metadata'] = {
            revenue: { confidence: 0.9, source: 'table', match_semantics: 'exact', inference_mode: 'direct' },
            net_profit: { confidence: 0.6, source: 'text', match_semantics: 'keyword_match', inference_mode: 'direct' },
            equity: { confidence: 0.59, source: 'derived' },
        };

        expect(countReliableMetrics(metadata, 0.6)).toBe(2);
    });

    it('keeps authoritative overrides even below threshold', () => {
        expect(
            survivesConfidenceFilter({
                confidence: 0.1,
                source: 'issuer_fallback',
                evidence_version: 'v2',
                match_semantics: 'not_applicable',
                inference_mode: 'policy_override',
                authoritative_override: true,
                reason_code: 'issuer_repo_override',
            })
        ).toBe(true);
    });
});
