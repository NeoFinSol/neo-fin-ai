import React, { useState } from 'react';
import {
  Paper, PasswordInput, Button, Title, Text,
  Container, Stack, Box, Center, ThemeIcon, Alert
} from '@mantine/core';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Shield, ArrowRight, AlertCircle, CheckCircle } from 'lucide-react';
import axios from 'axios';

export const Auth = () => {
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [valid, setValid] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) {
      setError('Введите API ключ');
      return;
    }

    setLoading(true);
    setError(null);
    setValid(false);

    try {
      // Validate key against real backend endpoint
      // One-shot axios instance — bypasses apiClient interceptors so we test exactly the entered key
      // Use Vite proxy (/api → http://localhost:8000) to avoid CORS issues in dev
      await axios.get('/api/analyses?page=1&page_size=1', {
        headers: { 'X-API-Key': apiKey.trim() },
        timeout: 10000,
      });
      setValid(true);
      login(apiKey.trim());
      navigate(from, { replace: true });
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 401 || status === 403) {
        setError('Невалидный ключ. Проверьте правильность и попробуйте снова.');
      } else {
        setError('Не удалось подключиться к серверу. Проверьте соединение.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box bg="#f8f9fa" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Center pt={80} pb={40}>
        <Stack align="center" gap="xs">
          <Box
            bg="#00288e"
            p={12}
            style={{ borderRadius: 12, boxShadow: '0 8px 16px rgba(0, 40, 142, 0.2)' }}
          >
            <Shield size={32} color="white" />
          </Box>
          <Title order={1} style={{ letterSpacing: '-0.02em', fontWeight: 800 }}>NeoFin AI</Title>
          <Text c="dimmed" size="sm">Платформа финансового анализа</Text>
        </Stack>
      </Center>

      <Container size={420}>
        <Paper
          radius="md"
          p="xl"
          bg="white"
          style={{ boxShadow: '0 12px 40px rgba(25, 28, 29, 0.06)', border: 'none' }}
        >
          <Title order={2} size="h3" mb={4}>Вход в систему</Title>
          <Text c="dimmed" size="sm" mb="xl">
            Введите API ключ для доступа к платформе
          </Text>

          <form onSubmit={handleSubmit}>
            <Stack gap="md">
              <Box>
                <Text size="xs" fw={700} mb={8} style={{ letterSpacing: '0.05em' }}>
                  API КЛЮЧ
                </Text>
                <PasswordInput
                  placeholder="neofin_••••••••••••••••"
                  value={apiKey}
                  onChange={(e) => {
                    setApiKey(e.currentTarget.value);
                    setError(null);
                    setValid(false);
                  }}
                  disabled={loading}
                  rightSection={
                    valid ? (
                      <ThemeIcon color="teal" variant="transparent" size="sm">
                        <CheckCircle size={16} />
                      </ThemeIcon>
                    ) : null
                  }
                  styles={{
                    input: {
                      backgroundColor: '#f3f4f5',
                      border: error ? '1px solid #fa5252' : valid ? '1px solid #12b886' : 'none',
                      height: 48,
                    },
                    innerInput: { height: 48 },
                  }}
                />
              </Box>

              {error && (
                <Alert
                  icon={<AlertCircle size={16} />}
                  color="red"
                  variant="light"
                  radius="md"
                  p="sm"
                >
                  <Text size="sm">{error}</Text>
                </Alert>
              )}

              <Button
                type="submit"
                fullWidth
                size="lg"
                radius="md"
                loading={loading}
                rightSection={!loading ? <ArrowRight size={18} /> : null}
                style={{
                  background: 'linear-gradient(135deg, #00288e 0%, #1e40af 100%)',
                  border: 'none',
                  height: 54,
                }}
              >
                {loading ? 'Проверка ключа...' : 'Войти'}
              </Button>
            </Stack>
          </form>
        </Paper>
      </Container>

      <Box mt="auto" p="xl" style={{ borderTop: '1px solid #f3f4f5' }}>
        <Text ta="center" size="xs" c="dimmed">© 2024 NEOFIN AI. ALL RIGHTS RESERVED.</Text>
      </Box>
    </Box>
  );
};
