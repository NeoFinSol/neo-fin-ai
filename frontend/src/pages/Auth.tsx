import React, { useState } from 'react';
import { 
  Paper, 
  TextInput, 
  PasswordInput, 
  Checkbox, 
  Button, 
  Title, 
  Text, 
  Anchor, 
  Group, 
  Container, 
  Tabs, 
  Stack, 
  Box, 
  Center, 
  Image, 
  Transition 
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Shield, ArrowRight } from 'lucide-react';

export const Auth = () => {
  const [activeTab, setActiveTab] = useState<string | null>('login');
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';

  const form = useForm({
    initialValues: {
      email: '',
      password: '',
      terms: true,
    },

    validate: {
      email: (value) => (/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(value) ? null : 'Введите корректный адрес электронной почты'),
      password: (value) => (value.length < 6 ? 'Пароль должен быть не менее 6 символов' : null),
      terms: (value) => (activeTab === 'register' && !value ? 'Необходимо принять условия использования' : null),
    },
  });

  const handleSubmit = (values: typeof form.values) => {
    // Get API key from environment or show demo key
    const apiKey = import.meta.env.VITE_DEV_API_KEY || 'dev_test_key_12345';

    // In production, you would validate credentials against backend
    // For now, we use the dev key for demonstration
    login(apiKey);
    navigate(from, { replace: true });
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
        </Stack>
      </Center>

      <Container size={420}>
        <Paper 
          radius="md" 
          p="xl" 
          bg="white" 
          style={{ 
            boxShadow: '0 12px 40px rgba(25, 28, 29, 0.06)',
            border: 'none'
          }}
        >
          <Tabs value={activeTab} onChange={setActiveTab} variant="pills" radius="xl" mb="xl">
            <Tabs.List grow>
              <Tabs.Tab value="login" px="xl">Вход</Tabs.Tab>
              <Tabs.Tab value="register" px="xl">Регистрация</Tabs.Tab>
            </Tabs.List>
          </Tabs>

          <Title order={2} size="h3" mb={4}>
            {activeTab === 'login' ? 'Вход в NeoFin AI' : 'Создать аккаунт'}
          </Title>
          <Text c="dimmed" size="sm" mb="xl">
            {activeTab === 'login' 
              ? 'Введите свои данные для доступа к платформе' 
              : 'Начните анализировать финансовые отчеты сегодня'}
          </Text>

          <form onSubmit={form.onSubmit(handleSubmit)}>
            <Stack gap="md">
              <TextInput
                label="EMAIL"
                placeholder="name@company.com"
                required
                {...form.getInputProps('email')}
                styles={{
                  label: { fontSize: 10, fontWeight: 700, letterSpacing: '0.05em', marginBottom: 8 },
                  input: { backgroundColor: '#f3f4f5', border: 'none', height: 48 }
                }}
              />

              <Box>
                <Group justify="space-between" mb={8}>
                  <Text component="label" size="xs" fw={700} style={{ letterSpacing: '0.05em' }}>ПАРОЛЬ</Text>
                  <Anchor component="button" size="xs" c="dimmed" fw={500}>Забыли пароль?</Anchor>
                </Group>
                <PasswordInput
                  placeholder="••••••••"
                  required
                  {...form.getInputProps('password')}
                  styles={{
                    input: { backgroundColor: '#f3f4f5', border: 'none', height: 48 },
                    innerInput: { height: 48 }
                  }}
                />
              </Box>

              {activeTab === 'register' && (
                <Checkbox
                  label="Я согласен с условиями использования"
                  {...form.getInputProps('terms', { type: 'checkbox' })}
                />
              )}

              <Button 
                type="submit" 
                fullWidth 
                size="lg"
                radius="md"
                rightSection={<ArrowRight size={18} />}
                style={{
                  background: 'linear-gradient(135deg, #00288e 0%, #1e40af 100%)',
                  transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                  border: 'none',
                  height: 54
                }}
                className="hover:scale-[1.02] hover:shadow-lg"
              >
                {activeTab === 'login' ? 'Войти' : 'Зарегистрироваться'}
              </Button>
            </Stack>
          </form>

          <Box mt="xl" style={{ position: 'relative' }}>
            <Box style={{ borderTop: '1px solid #f3f4f5', position: 'absolute', top: '50%', left: 0, right: 0 }} />
            <Center style={{ position: 'relative' }}>
              <Text size="xs" bg="white" px="md" c="dimmed" fw={500} style={{ textTransform: 'uppercase', letterSpacing: '0.1em' }}>ИЛИ</Text>
            </Center>
          </Box>

          <Button 
            variant="default" 
            fullWidth 
            mt="xl" 
            size="lg"
            radius="md"
            leftSection={<Image src="https://www.google.com/favicon.ico" w={18} h={18} />}
            styles={{
              root: { backgroundColor: '#191c1d', border: 'none', height: 54, color: '#ffffff' }
            }}
          >
            Войти через Google
          </Button>

          <Text ta="center" mt="xl" size="sm">
            {activeTab === 'login' ? 'Нет аккаунта?' : 'Уже есть аккаунт?'} {' '}
            <Anchor 
              component="button" 
              type="button" 
              fw={700} 
              onClick={() => setActiveTab(activeTab === 'login' ? 'register' : 'login')}
            >
              {activeTab === 'login' ? 'Зарегистрироваться' : 'Войти'}
            </Anchor>
          </Text>
        </Paper>
      </Container>

      <Center mt="auto" pb="xl">
        <Group gap="xl" opacity={0.5}>
          <Text size="xs" fw={700} style={{ letterSpacing: '0.1em' }}>AES-256 ENCRYPTED</Text>
        </Group>
      </Center>

      <Box p="xl" style={{ borderTop: '1px solid #f3f4f5' }}>
        <Group justify="space-between">
          <Text size="xs" c="dimmed">© 2024 NEOFIN AI. ALL RIGHTS RESERVED.</Text>
          <Group gap="xl">
            <Anchor size="xs" c="dimmed">ENGLISH (US)</Anchor>
            <Anchor size="xs" c="dimmed">PRIVACY</Anchor>
            <Anchor size="xs" c="dimmed">TERMS</Anchor>
          </Group>
        </Group>
      </Box>
    </Box>
  );
};
