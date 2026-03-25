import axios from 'axios';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000,
});

apiClient.interceptors.request.use((config) => {
  if (import.meta.env.DEV) {
    console.log('API Request:', config.method, config.url);
  }
  const apiKey = localStorage.getItem('neofin_api_key');
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => {
    if (import.meta.env.DEV) {
      console.log('API Response:', response.status, response.config.url);
    }
    return response;
  },
  (error) => {
    if (import.meta.env.DEV) {
      console.error('API Error:', error.message, error.response?.status, error.response?.data);
    }
    if (error.response?.status === 401) {
      localStorage.removeItem('neofin_api_key');
    }
    return Promise.reject(error);
  }
);
