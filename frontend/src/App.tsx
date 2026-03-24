import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';
import '@mantine/dropzone/styles.css';

import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { theme } from './theme/theme';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { AnalysisHistory } from './pages/AnalysisHistory';
import { SettingsPage } from './pages/SettingsPage';
import { Auth } from './pages/Auth';
import { NotFound } from './pages/NotFound';
import { AuthProvider } from './context/AuthContext';
import { HistoryProvider } from './context/AnalysisHistoryContext';
import { ProtectedRoute } from './components/ProtectedRoute';

export default function App() {
  return (
    <MantineProvider theme={theme}>
      <Notifications position="top-right" zIndex={2000} />
      <AuthProvider>
        <HistoryProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<Auth />} />
              
              <Route path="/" element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }>
                <Route index element={<Dashboard />} />
                <Route path="history" element={<AnalysisHistory />} />
                <Route path="settings" element={<SettingsPage />} />
              </Route>

              <Route path="/404" element={<NotFound />} />
              <Route path="*" element={<Navigate to="/404" replace />} />
            </Routes>
          </BrowserRouter>
        </HistoryProvider>
      </AuthProvider>
    </MantineProvider>
  );
}

