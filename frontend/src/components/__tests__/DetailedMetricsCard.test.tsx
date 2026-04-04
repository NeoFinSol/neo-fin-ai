import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MantineProvider } from '@mantine/core';

import DetailedMetricsCard from '../report/DetailedMetricsCard';

describe('DetailedMetricsCard', () => {
    it('shows reliable metrics count without impossible denominator copy', () => {
        render(
            <MantineProvider>
                <DetailedMetricsCard
                    metrics={{
                        revenue: 1000,
                        net_profit: 100,
                        total_assets: 2000,
                        equity: 500,
                    } as never}
                    extractionMetadata={{
                        revenue: { confidence: 0.9, source: 'table', match_semantics: 'exact', inference_mode: 'direct' },
                        net_profit: { confidence: 0.9, source: 'table', match_semantics: 'exact', inference_mode: 'direct' },
                        total_assets: { confidence: 0.9, source: 'table', match_semantics: 'exact', inference_mode: 'direct' },
                        equity: { confidence: 0.9, source: 'table', match_semantics: 'exact', inference_mode: 'direct' },
                    }}
                    reliableCount={4}
                />
            </MantineProvider>,
        );

        expect(screen.getByText(/Надёжно извлечено:/i)).toBeInTheDocument();
        expect(screen.getByText(/4 показател/)).toBeInTheDocument();
        expect(screen.queryByText(/из 15/i)).not.toBeInTheDocument();
    });
});
