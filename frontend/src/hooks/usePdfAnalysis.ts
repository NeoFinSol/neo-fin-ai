import { useState, useCallback } from 'react';
import { apiClient } from '../api/client';
import { notifications } from '@mantine/notifications';
import { AnalysisData } from '../api/interfaces';

export const usePdfAnalysis = () => {
  const [status, setStatus] = useState<'idle' | 'uploading' | 'processing' | 'completed' | 'failed'>('idle');
  const [result, setResult] = useState<AnalysisData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const analyze = useCallback(async (file: File) => {
    console.log('Starting file analysis:', file.name, file.size, file.type);
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
      console.log('Sending request to backend...');
      setStatus('processing');
      notifications.update({
        id: 'pdf-analysis',
        title: 'Обработка данных',
        message: 'ИИ анализирует финансовые показатели...',
        loading: true,
      });

      const response = await apiClient.post<AnalysisData>('/analyze/pdf/file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000, // 5 минут для больших файлов
      });

      console.log('Received response from backend:', response.data);
      setStatus('completed');
      setResult(response.data);

      notifications.update({
        id: 'pdf-analysis',
        title: 'Анализ завершен',
        message: 'Финансовый отчет успешно обработан',
        color: 'green',
        loading: false,
        autoClose: 5000,
      });
    } catch (err: any) {
      console.error('Error during analysis:', err);
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
    setError(null);
  }, []);

  return {
    mutate: analyze,
    isPending: status === 'uploading' || status === 'processing',
    statusText: status === 'uploading' ? 'Загрузка...' : status === 'processing' ? 'Анализ...' : '',
    isError: status === 'failed',
    error,
    data: result,
    reset,
    progressStep: status,
  };
};
