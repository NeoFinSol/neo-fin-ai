import { useState, useCallback, useRef, useEffect } from 'react';
import { apiClient } from '../api/client';
import { AnalysisResponse, UploadResponse, AnalysisStatus, AnalysisData } from '../api/interfaces';
import { notifications } from '@mantine/notifications';

export const usePdfAnalysis = () => {
  const [status, setStatus] = useState<AnalysisStatus | 'idle'>('idle');
  const [result, setResult] = useState<AnalysisData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollingRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const pollResult = useCallback(async (taskId: string) => {
    stopPolling();
    
    pollingRef.current = window.setInterval(async () => {
      try {
        const response = await apiClient.get<AnalysisResponse>(`/result/${taskId}`);
        const { status: currentStatus, data, error: apiError } = response.data;

        setStatus(currentStatus);

        if (currentStatus === 'completed' && data) {
          setResult(data);
          stopPolling();
          notifications.update({
            id: 'pdf-analysis',
            title: 'Анализ завершен',
            message: 'Финансовый отчет успешно обработан',
            color: 'green',
            loading: false,
            autoClose: 5000,
          });
        } else if (currentStatus === 'failed') {
          setError(apiError || 'Ошибка обработки');
          stopPolling();
          notifications.update({
            id: 'pdf-analysis',
            title: 'Ошибка анализа',
            message: apiError || 'Не удалось проанализировать файл',
            color: 'red',
            loading: false,
            autoClose: 5000,
          });
        }
      } catch (err: any) {
        console.error('Polling error:', err);
        const msg = err.response?.data?.detail || 'Потеряно соединение с сервером';
        setError(msg);
        setStatus('failed');
        stopPolling();
        notifications.update({
          id: 'pdf-analysis',
          title: 'Ошибка соединения',
          message: msg,
          color: 'red',
          loading: false,
          autoClose: 5000,
        });
      }
    }, 2000);
  }, [stopPolling]);

  const uploadPdf = async (file: File) => {
    setStatus('uploading');
    setError(null);
    setResult(null);

    notifications.show({
      id: 'pdf-analysis',
      title: 'Загрузка файла',
      message: `Загружаем ${file.name}...`,
      loading: true,
      autoClose: false,
      withCloseButton: false,
    });

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await apiClient.post<UploadResponse>('/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const { task_id } = response.data;
      setStatus('processing');
      
      notifications.update({
        id: 'pdf-analysis',
        title: 'Обработка данных',
        message: 'ИИ анализирует финансовые показатели...',
        loading: true,
        autoClose: false,
      });

      pollResult(task_id);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Ошибка при загрузке файла';
      setError(msg);
      setStatus('failed');
      notifications.update({
        id: 'pdf-analysis',
        title: 'Ошибка загрузки',
        message: msg,
        color: 'red',
        loading: false,
        autoClose: 5000,
      });
    }
  };

  return {
    uploadPdf,
    status,
    result,
    error,
    isIdle: status === 'idle',
    isProcessing: status === 'processing' || status === 'pending' || status === 'uploading',
  };
};
