// frontend/src/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { MantineProvider, createTheme } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import App from './App';

// Импорт стилей Mantine
import '@mantine/core/styles.css';
import '@mantine/dropzone/styles.css';
import '@mantine/notifications/styles.css';

// === ENVIRONMENT VALIDATION ===
// Предупреждение, если разработчик забыл настроить .env файл
if (import.meta.env.DEV && !import.meta.env.VITE_API_KEY) {
  console.warn('⚠️ VITE_API_KEY not set - using DEV_MODE. Backend must have DEV_MODE=1 to accept requests without key.');
}

// Тема Mantine (можно настроить под дизайн-систему конкурса)
const theme = createTheme({
  primaryColor: 'blue',
  fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
  headings: {
    fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
  },
  components: {
    // Глобальные переопределения компонентов, если нужны
    Button: {
      defaultProps: {
        radius: 'md',
      },
    },
    Card: {
      defaultProps: {
        radius: 'md',
        shadow: 'sm',
      },
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <MantineProvider theme={theme}>
      <Notifications position="top-right" />
      <App />
    </MantineProvider>
  </React.StrictMode>
);
