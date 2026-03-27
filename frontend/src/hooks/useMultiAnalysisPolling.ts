import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import { MultiAnalysisResponse, PeriodResult, MultiAnalysisProgress } from '../api/interfaces';

const POLL_INTERVAL_MS = 2500;

export interface MultiAnalysisPollingState {
    status: 'idle' | 'processing' | 'completed' | 'failed';
    periods: PeriodResult[] | null;
    progress: MultiAnalysisProgress | null;
}

export function useMultiAnalysisPolling(sessionId: string | undefined): MultiAnalysisPollingState {
    const [state, setState] = useState<MultiAnalysisPollingState>({
        status: 'idle',
        periods: null,
        progress: null,
    });

    useEffect(() => {
        if (!sessionId) return;

        setState({ status: 'processing', periods: null, progress: null });

        let timeoutId: ReturnType<typeof setTimeout>;
        let cancelled = false;

        const fetchOnce = async () => {
            if (cancelled) return;

            try {
                const { data } = await apiClient.get<MultiAnalysisResponse>(
                    `/multi-analysis/${sessionId}`
                );

                if (cancelled) return;

                if (data.status === 'completed') {
                    setState({ status: 'completed', periods: data.periods, progress: null });
                    return; // stop polling
                }

                // status === 'processing'
                setState((prev) => ({
                    ...prev,
                    status: 'processing',
                    progress: 'progress' in data ? data.progress : prev.progress,
                }));
            } catch (err: unknown) {
                if (cancelled) return;
                const httpStatus = (err as { response?: { status?: number } })?.response?.status;
                if (httpStatus === 404 || httpStatus === 422) {
                    setState({ status: 'failed', periods: null, progress: null });
                    return; // stop polling
                }
                // transient network error — schedule next poll anyway
            }

            if (!cancelled) {
                timeoutId = setTimeout(fetchOnce, POLL_INTERVAL_MS);
            }
        };

        timeoutId = setTimeout(fetchOnce, 0); // start immediately

        return () => {
            cancelled = true;
            clearTimeout(timeoutId);
        };
    }, [sessionId]);

    return state;
}
