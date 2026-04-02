import React from 'react';
import { Container, Title, Text, Button, Stack, Center, Box } from '@mantine/core';
import { useNavigate } from 'react-router-dom';
import { Home, AlertCircle } from 'lucide-react';

export const NotFound = () => {
  const navigate = useNavigate();

  return (
    <Box bg="#f8f9fa" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center' }}>
      <Container size="sm">
        <Stack align="center" gap="xl" ta="center">
          <Box 
            bg="#ffdad6" 
            p={24} 
            style={{ borderRadius: '50%', boxShadow: '0 8px 16px rgba(186, 26, 26, 0.1)' }}
          >
            <AlertCircle size={48} color="#ba1a1a" />
          </Box>
          
          <Stack gap="xs">
            <Title order={1} style={{ letterSpacing: '-0.02em', fontWeight: 800, fontSize: 48 }}>Ошибка 404</Title>
            <Text size="xl" c="dimmed" fw={500}>Страница не найдена</Text>
          </Stack>

          <Text size="md" c="dimmed" maw={400}>
            К сожалению, запрашиваемая вами страница не существует или была перемещена.
          </Text>

          <Button 
            size="lg" 
            radius="md" 
            leftSection={<Home size={18} />}
            onClick={() => navigate('/')}
            style={{
              background: 'linear-gradient(135deg, #00288e 0%, #1e40af 100%)',
              border: 'none',
              height: 54,
              paddingLeft: 32,
              paddingRight: 32
            }}
          >
            Вернуться на главную
          </Button>
        </Stack>
      </Container>
    </Box>
  );
};
