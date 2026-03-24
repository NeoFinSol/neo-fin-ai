import React, { createContext, useContext, useState, useCallback } from 'react';
import { apiClient } from '../api/client';
import { AnalysisData } from '../api/interfaces';
import { notifications } from '@mantine/notifications';

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

        try {
            setStatus('processing');
            notifications.update({
                id: 'pdf-analysis',
                title: 'Обработка данных',
                message: 'ИИ анализирует финансовые показатели...',
                loading: true,
            });

            const response = await apiClient.post<AnalysisData>('/analyze/pdf/file', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                timeout: 300000,
            });

            setResult(response.data);
            setStatus('completed');

            notifications.update({
                id: 'pdf-analysis',
                title: 'Анализ завершен',
                message: 'Финансовый отчет успешно обработан',
                color: 'green',
                loading: false,
                autoClose: 5000,
            });
        } catch (err: any) {
            const msg = err.response?.data?.detail || err.message || 'Ошибка при анализе файла';
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
