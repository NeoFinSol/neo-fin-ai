import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import { apiClient } from '../api/client';
import { AnalysisData } from '../api/interfaces';
import { notifications } from '@mantine/notifications';

const MAX_POLLING_ATTEMPTS = 15;
const POLLING_INTERVAL = 2000;

type AnalysisStatus = 'idle' | 'uploading' | 'processing' | 'completed' | 'failed';

interface AnalysisContextType {
    status: AnalysisStatus;
    result: AnalysisData | null;
    filename: string;
    error: string | null;
    analyze: (file: File) => Promise<void>;
    reset: () => void;
}

const AnalysisContext = createContext<AnalysisContextType | undefined>(undefined);

export const AnalysisProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [status, setStatus] = useState<AnalysisStatus>('idle');
    const [result, setResult] = useState<AnalysisData | null>(null);
    const [filename, setFilename] = useState('');
    const [error, setError] = useState<string | null>(null);
    const timeoutId = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

    useEffect(() => {
        return () => {
            clearTimeout(timeoutId.current);
        };
    }, []);

    const analyze = useCallback(async (file: File) => {
        setFilename(file.name);
        setStatus('uploading');
        setError(null);
        setResult(null);

        notifications.show({
            id: 'pdf-analysis',
            title: 'Загрузка файла',
            message: `Загружаем ${file.name}...`,
            loading: true,
            autoClose: false,
        });

        const formData = new FormData();
        formData.append('file', file);

        let cancelled = false;

        try {
            const uploadResponse = await apiClient.post<{ task_id: string }>('/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });

            const taskId = uploadResponse.data.task_id;

            setStatus('processing');
            notifications.update({
                id: 'pdf-analysis',
                title: 'Обработка данных',
                message: 'ИИ анализирует финансовые показатели...',
                loading: true,
            });

            let attempts = 0;

            const poll = async () => {
                if (cancelled) return;

                if (attempts >= MAX_POLLING_ATTEMPTS) {
                    const msg = 'Превышено максимальное количество попыток опроса';
                    setError(msg);
                    setStatus('failed');
                    notifications.update({
                        id: 'pdf-analysis',
                        title: 'Ошибка анализа',
                        message: msg,
                        color: 'red',
                        loading: false,
                        autoClose: 5000,
                    });
                    return;
                }

                attempts += 1;

                try {
                    const pollResponse = await apiClient.get<{ status: string; result?: AnalysisData }>(`/result/${taskId}`);
                    const taskStatus = pollResponse.data.status;

                    if (cancelled) return;

                    if (taskStatus === 'completed') {
                        setResult(pollResponse.data.result ?? null);
                        setStatus('completed');
                        notifications.update({
                            id: 'pdf-analysis',
                            title: 'Анализ завершен',
                            message: 'Финансовый отчет успешно обработан',
                            color: 'green',
                            loading: false,
                            autoClose: 5000,
                        });
                    } else if (taskStatus === 'failed') {
                        const msg = 'Задача завершилась с ошибкой';
                        setError(msg);
                        setStatus('failed');
                        notifications.update({
                            id: 'pdf-analysis',
                            title: 'Ошибка анализа',
                            message: msg,
                            color: 'red',
                            loading: false,
                            autoClose: 5000,
                        });
                    } else {
                        // still processing — schedule next poll
                        timeoutId.current = setTimeout(poll, POLLING_INTERVAL);
                    }
                } catch (err: unknown) {
                    if (cancelled) return;

                    const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } };
                    const httpStatus = axiosErr?.response?.status;

                    if (httpStatus === 404) {
                        const msg = 'Задача не найдена';
                        setError(msg);
                        setStatus('failed');
                        notifications.update({
                            id: 'pdf-analysis',
                            title: 'Ошибка анализа',
                            message: msg,
                            color: 'red',
                            loading: false,
                            autoClose: 5000,
                        });
                    } else if (httpStatus !== undefined && httpStatus >= 500) {
                        // 5xx — retry
                        timeoutId.current = setTimeout(poll, POLLING_INTERVAL);
                    } else {
                        // network error or other — retry
                        timeoutId.current = setTimeout(poll, POLLING_INTERVAL);
                    }
                }
            };

            timeoutId.current = setTimeout(poll, POLLING_INTERVAL);
        } catch (err: unknown) {
            if (cancelled) return;
            const axiosMsg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
            const finalMsg = axiosMsg || (err instanceof Error ? err.message : 'Ошибка при загрузке файла');
            setError(finalMsg);
            setStatus('failed');
            notifications.update({
                id: 'pdf-analysis',
                title: 'Ошибка анализа',
                message: finalMsg,
                color: 'red',
                loading: false,
                autoClose: 5000,
            });
        }
    }, []);

    const reset = useCallback(() => {
        setStatus('idle');
        setResult(null);
        setFilename('');
        setError(null);
    }, []);

    return (
        <AnalysisContext.Provider value={{ status, result, filename, error, analyze, reset }}>
            {children}
        </AnalysisContext.Provider>
    );
};

export const useAnalysis = () => {
    const ctx = useContext(AnalysisContext);
    if (!ctx) throw new Error('useAnalysis must be used inside AnalysisProvider');
    return ctx;
};
