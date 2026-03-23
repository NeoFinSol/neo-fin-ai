import axios from 'axios';

export const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000, // 120 секунд для AI анализа
});

apiClient.interceptors.request.use((config) => {
  const apiKey = localStorage.getItem('neofin_api_key');
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('neofin_api_key');
      // Для MVP - просто логгируем ошибку, не редиректим
      console.error('API Key invalid or missing');
    }
    return Promise.reject(error);
  }
);
