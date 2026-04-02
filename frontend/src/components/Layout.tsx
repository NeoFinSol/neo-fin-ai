import React from 'react';
import { Outlet, Link } from 'react-router-dom';
import {
  AppShell,
  Burger,
  Group,
  Text,
  Box,
  Stack,
  NavLink,
  Container,
  Divider,
  useMantineColorScheme,
  ActionIcon,
  Tooltip,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  LayoutDashboard,
  History,
  Settings,
  LogOut,
  Shield,
  Moon,
  Sun,
} from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { AppFooter } from './AppFooter';
import { ECOSYSTEM_NAME, PRODUCT_NAME } from '../constants/branding';

export const Layout = () => {
  const [opened, { toggle, close }] = useDisclosure(false);
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();
  const { logout } = useAuth();

  const handleLogout = () => {
    logout();
  };

  const navItems = [
    { icon: LayoutDashboard, label: 'Главная', path: '/' },
    { icon: History, label: 'История', path: '/history' },
    { icon: Settings, label: 'Настройки', path: '/settings' },
  ];

  return (
    <AppShell
      header={{ height: 64 }}
      navbar={{
        width: { base: 280, sm: 300, lg: 320 },
        breakpoint: 'sm',
        collapsed: { mobile: !opened },
      }}
      padding="md"
      styles={{
        main: {
          background: 'radial-gradient(circle at top, rgba(0, 40, 142, 0.08), transparent 38%), #f7f8fc',
          minHeight: '100vh',
        },
        header: {
          backgroundColor: 'rgba(255, 255, 255, 0.94)',
          borderBottom: '1px solid rgba(0, 0, 0, 0.05)',
          backdropFilter: 'blur(8px)',
        },
      }}
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="sm">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Group gap="xs">
              <Box
                bg="#00288e"
                p={8}
                style={{ borderRadius: 10, boxShadow: '0 10px 18px rgba(0, 40, 142, 0.18)' }}
              >
                <Shield size={20} color="white" />
              </Box>
              <Stack gap={0}>
                <Text
                  fw={800}
                  size="lg"
                  style={{
                    letterSpacing: '-0.02em',
                    color: '#00288e',
                    lineHeight: 1.1,
                  }}
                >
                  {PRODUCT_NAME}
                </Text>
                <Text size="xs" c="dimmed">
                  Модуль экосистемы {ECOSYSTEM_NAME}
                </Text>
              </Stack>
            </Group>
          </Group>

          <Tooltip label={colorScheme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}>
            <ActionIcon
              variant="subtle"
              color="gray"
              onClick={() => toggleColorScheme()}
              size="lg"
            >
              {colorScheme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
            </ActionIcon>
          </Tooltip>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md" style={{ backgroundColor: 'rgba(255, 255, 255, 0.95)' }}>
        <AppShell.Section>
          <Group gap="xs" mb="lg">
            <Text size="xs" fw={700} c="dimmed" style={{ letterSpacing: '0.1em' }}>
              Меню
            </Text>
          </Group>
          <Stack gap="xs">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                component={Link}
                to={item.path}
                label={item.label}
                leftSection={<item.icon size={18} strokeWidth={2} />}
                onClick={close}
                styles={{
                  root: {
                    borderRadius: 12,
                    paddingBlock: 10,
                    '&[dataActive]': {
                      backgroundColor: 'rgba(0, 40, 142, 0.1)',
                      color: '#00288e',
                    },
                    '&:hover': {
                      backgroundColor: 'rgba(0, 40, 142, 0.05)',
                    },
                  },
                  label: {
                    fontWeight: 600,
                  },
                }}
              />
            ))}
          </Stack>
        </AppShell.Section>

        <AppShell.Section grow>
          <Divider my="md" />
        </AppShell.Section>

        <AppShell.Section>
          <NavLink
            component="button"
            onClick={handleLogout}
            label="Выход"
            leftSection={<LogOut size={18} strokeWidth={2} />}
            styles={{
              root: {
                borderRadius: 12,
                color: '#dc3545',
                '&:hover': {
                  backgroundColor: 'rgba(220, 53, 69, 0.1)',
                },
              },
              label: {
                fontWeight: 600,
              },
            }}
          />
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Main>
        <Container size="xl" py="lg" style={{ minHeight: 'calc(100vh - 64px)' }}>
          <Stack justify="space-between" style={{ minHeight: 'calc(100vh - 112px)' }}>
            <Outlet />
            <AppFooter />
          </Stack>
        </Container>
      </AppShell.Main>
    </AppShell>
  );
};
