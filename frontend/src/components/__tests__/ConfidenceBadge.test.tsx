import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { MantineProvider } from '@mantine/core';
import ConfidenceBadge from '../ConfidenceBadge';
import { ExtractionSource } from '../../api/interfaces';

// Wrapper with MantineProvider
const wrapper = ({ children }: { children: React.ReactNode }) => (
    <MantineProvider>{children}</MantineProvider>
);

describe('ConfidenceBadge', () => {
    describe('Color coding by confidence level', () => {
        it('displays green badge for high confidence (> 0.8)', () => {
            render(
                <ConfidenceBadge
                    metricKey="revenue"
                    confidence={0.9}
                    source="table_exact"
                />,
                { wrapper }
            );

            expect(screen.getByText('0.90')).toBeInTheDocument();
            const confidenceText = screen.getByText('0.90');
            expect(confidenceText).toHaveStyle('color: #2f9e44');
        });

        it('displays yellow badge for medium confidence (0.5–0.8)', () => {
            render(
                <ConfidenceBadge
                    metricKey="profit"
                    confidence={0.7}
                    source="table_partial"
                />,
                { wrapper }
            );

            const confidenceText = screen.getByText('0.70');
            expect(confidenceText).toHaveStyle('color: #e67700');
        });

        it('displays red badge for low confidence (< 0.5)', () => {
            render(
                <ConfidenceBadge
                    metricKey="assets"
                    confidence={0.3}
                    source="derived"
                />,
                { wrapper }
            );

            const confidenceText = screen.getByText('0.30');
            expect(confidenceText).toHaveStyle('color: #c92a2a');
        });
    });

    describe('Emoji indicators', () => {
        it('shows green circle emoji for high confidence', () => {
            render(
                <ConfidenceBadge
                    metricKey="revenue"
                    confidence={0.95}
                    source="table_exact"
                />,
                { wrapper }
            );

            expect(screen.getByText('🟢')).toBeInTheDocument();
        });

        it('shows yellow circle emoji for medium confidence', () => {
            render(
                <ConfidenceBadge
                    metricKey="revenue"
                    confidence={0.6}
                    source="table_partial"
                />,
                { wrapper }
            );

            expect(screen.getByText('🟡')).toBeInTheDocument();
        });

        it('shows red circle emoji for low confidence', () => {
            render(
                <ConfidenceBadge
                    metricKey="revenue"
                    confidence={0.2}
                    source="derived"
                />,
                { wrapper }
            );

            expect(screen.getByText('🔴')).toBeInTheDocument();
        });
    });

    describe('Tooltip content', () => {
        it('shows tooltip on hover with source information', async () => {
            render(
                <ConfidenceBadge
                    metricKey="revenue"
                    confidence={0.9}
                    source="table_exact"
                />,
                { wrapper }
            );

            const badge = screen.getByText('0.90').closest('span');
            if (badge) {
                await userEvent.hover(badge);
            }

            await waitFor(() => {
                expect(screen.getByText(/Источник:/i)).toBeInTheDocument();
            });
        });

        it('tooltip contains all three required sections', async () => {
            render(
                <ConfidenceBadge
                    metricKey="equity"
                    confidence={0.85}
                    source="table_exact"
                />,
                { wrapper }
            );

            const badge = screen.getByText('0.85').closest('span');
            if (badge) {
                await userEvent.hover(badge);
            }

            await waitFor(() => {
                expect(screen.getByText(/Источник:/i)).toBeInTheDocument();
                expect(screen.getByText(/Метод:/i)).toBeInTheDocument();
                expect(screen.getByText(/Уверенность:/i)).toBeInTheDocument();
            });
        });
    });

    describe('Edge cases', () => {
        it('handles confidence value of 0', () => {
            render(
                <ConfidenceBadge
                    metricKey="revenue"
                    confidence={0}
                    source="derived"
                />,
                { wrapper }
            );

            expect(screen.getByText('0.00')).toBeInTheDocument();
        });

        it('handles confidence value of 1.0', () => {
            render(
                <ConfidenceBadge
                    metricKey="revenue"
                    confidence={1.0}
                    source="table_exact"
                />,
                { wrapper }
            );

            expect(screen.getByText('1.00')).toBeInTheDocument();
        });

        it('handles NaN confidence gracefully', () => {
            render(
                <ConfidenceBadge
                    metricKey="revenue"
                    confidence={NaN}
                    source="derived"
                />,
                { wrapper }
            );

            expect(screen.getByText('0.00')).toBeInTheDocument();
        });

        it('does not crash with component render', () => {
            expect(() =>
                render(
                    <ConfidenceBadge
                        metricKey="test"
                        confidence={0.9}
                        source="table_exact"
                    />,
                    { wrapper }
                )
            ).not.toThrow();
        });
    });
});
