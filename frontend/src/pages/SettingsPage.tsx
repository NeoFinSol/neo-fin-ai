import React from 'react';
import {
  ActionIcon,
  Avatar,
  Badge,
  Box,
  Button,
  Card,
  Group,
  Progress,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
  Tooltip,
  useMantineColorScheme,
} from '@mantine/core';
import {
  Check,
  Copy,
  CreditCard,
  Download,
  Key,
  Moon,
  Plus,
  Shield,
  Sun,
  Trash2,
  User,
} from 'lucide-react';
import { useClipboard } from '@mantine/hooks';

import { PRODUCT_NAME } from '../constants/branding';

const inputStyles = {
  label: { fontSize: 11, fontWeight: 700, letterSpacing: '0.05em', marginBottom: 8, color: '#6b7280' },
  input: { backgroundColor: 'white', border: '1px solid rgba(0, 0, 0, 0.06)', minHeight: 46, fontSize: 14 },
};

export const SettingsPage = () => {
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();
  const clipboard = useClipboard({ timeout: 2000 });

  const apiKey = import.meta.env.VITE_API_KEY || '****-****-****-****-****';
  const maskedApiKey = apiKey.length > 20 ? `${apiKey.substring(0, 4)}...${apiKey.substring(apiKey.length - 4)}` : apiKey;

  return (
    <Stack gap="xl">
      <Box>
        <Title order={1} style={{ letterSpacing: '-0.02em', fontWeight: 800 }}>Настройки</Title>
        <Text c="dimmed" size="lg">
          Управление профилем и параметрами сервиса {PRODUCT_NAME}
        </Text>
      </Box>

      <Tabs defaultValue="profile" orientation="vertical" variant="pills" radius="xl">
        <SimpleGrid cols={{ base: 1, md: 12 }} spacing="xl">
          <Box style={{ gridColumn: 'span 3' }}>
            <Tabs.List grow={false}>
              <Tabs.Tab value="profile" leftSection={<User size={18} />}>Профиль</Tabs.Tab>
              <Tabs.Tab value="security" leftSection={<Shield size={18} />}>Безопасность</Tabs.Tab>
              <Tabs.Tab value="api" leftSection={<Key size={18} />}>API-ключи</Tabs.Tab>
              <Tabs.Tab value="subscription" leftSection={<CreditCard size={18} />}>Тариф</Tabs.Tab>
            </Tabs.List>
          </Box>

          <Box style={{ gridColumn: 'span 9' }}>
            <Tabs.Panel value="profile">
              <Stack gap="xl">
                <Box>
                  <Title order={2} size="h3" mb={4}>Профиль</Title>
                  <Text c="dimmed" size="sm">Обновите личные данные и внешний вид рабочего пространства.</Text>
                </Box>

                <Card p="xl" radius="xl" bg="#f3f4f5">
                  <SimpleGrid cols={{ base: 1, lg: 4 }} spacing="xl">
                    <Stack align="center" gap="sm">
                      <Avatar
                        src="https://raw.githubusercontent.com/mantinedev/mantine/master/.demo/avatars/avatar-1.png"
                        size={104}
                        radius="xl"
                      />
                      <Button variant="subtle" size="xs">Изменить фото</Button>
                    </Stack>

                    <Stack gap="md" style={{ gridColumn: 'span 3' }}>
                      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
                        <TextInput label="ИМЯ" placeholder="Александр" defaultValue="Александр" styles={inputStyles} />
                        <TextInput label="ФАМИЛИЯ" placeholder="Иванов" defaultValue="Иванов" styles={inputStyles} />
                      </SimpleGrid>
                      <TextInput label="EMAIL" placeholder="alexander.i@neofin.ru" defaultValue="alexander.i@neofin.ru" styles={inputStyles} />
                      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
                        <TextInput label="КОМПАНИЯ" placeholder="НеоФин" defaultValue="НеоФин" styles={inputStyles} />
                        <TextInput label="РОЛЬ" placeholder="Финансовый директор" defaultValue="Финансовый директор" styles={inputStyles} />
                      </SimpleGrid>
                      <Group gap="md" wrap="wrap">
                        <Button variant="filled" bg="#00288e">
                          Сохранить изменения
                        </Button>
                        <Button variant="light" color="gray">
                          Отменить
                        </Button>
                      </Group>
                    </Stack>
                  </SimpleGrid>
                </Card>

                <Card p="xl" radius="xl" bg="#f3f4f5">
                  <Group justify="space-between" align="center" wrap="wrap">
                    <Box maw={520}>
                      <Text fw={600}>Внешний вид</Text>
                      <Text size="xs" c="dimmed">Переключайте тему интерфейса и подстраивайте рабочее пространство под себя.</Text>
                    </Box>
                    <ActionIcon
                      variant="outline"
                      color={colorScheme === 'dark' ? 'yellow' : 'blue'}
                      onClick={() => toggleColorScheme()}
                      size="lg"
                    >
                      {colorScheme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
                    </ActionIcon>
                  </Group>
                </Card>
              </Stack>
            </Tabs.Panel>

            <Tabs.Panel value="security">
              <Stack gap="xl">
                <Box>
                  <Title order={2} size="h3" mb={4}>Безопасность</Title>
                  <Text c="dimmed" size="sm">Управляйте паролем и защитой доступа к сервису.</Text>
                </Box>

                <Card p="xl" radius="xl" bg="#f3f4f5">
                  <Stack gap="md">
                    <TextInput label="ТЕКУЩИЙ ПАРОЛЬ" type="password" placeholder="••••••••" styles={inputStyles} />
                    <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
                      <TextInput label="НОВЫЙ ПАРОЛЬ" type="password" placeholder="••••••••" styles={inputStyles} />
                      <TextInput label="ПОДТВЕРЖДЕНИЕ" type="password" placeholder="••••••••" styles={inputStyles} />
                    </SimpleGrid>
                    <Group gap="md" wrap="wrap">
                      <Button variant="filled" bg="#00288e">Обновить пароль</Button>
                      <Button variant="light" color="gray">Сбросить</Button>
                    </Group>
                  </Stack>
                </Card>

                <Card p="xl" radius="xl" bg="#f3f4f5">
                  <Group justify="space-between" wrap="wrap" gap="lg">
                    <Box maw={520}>
                      <Text fw={600}>Двухфакторная аутентификация</Text>
                      <Text size="xs" c="dimmed">Добавьте дополнительный уровень защиты для входа в систему.</Text>
                    </Box>
                    <Switch size="md" color="blue" defaultChecked />
                  </Group>
                </Card>
              </Stack>
            </Tabs.Panel>

            <Tabs.Panel value="api">
              <Stack gap="xl">
                <Group justify="space-between" align="flex-start" wrap="wrap">
                  <Box>
                    <Title order={2} size="h3" mb={4}>API-ключи</Title>
                    <Text c="dimmed" size="sm">Управляйте доступом для ваших интеграций и внутренних модулей.</Text>
                  </Box>
                  <Button variant="light" leftSection={<Plus size={18} />}>Создать новый ключ</Button>
                </Group>

                <Card p={0} radius="xl" bg="#f3f4f5" style={{ overflow: 'hidden' }}>
                  <Table verticalSpacing="md" horizontalSpacing="xl">
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th style={{ border: 'none', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Название</Table.Th>
                        <Table.Th style={{ border: 'none', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Ключ</Table.Th>
                        <Table.Th style={{ border: 'none', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Создан</Table.Th>
                        <Table.Th style={{ border: 'none', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em' }} align="right">Действия</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      <Table.Tr>
                        <Table.Td style={{ border: 'none' }}><Text fw={600} size="sm">Продакшен</Text></Table.Td>
                        <Table.Td style={{ border: 'none' }}>
                          <Group gap="xs" wrap="wrap">
                            <Text size="xs" ff="JetBrains Mono" c="dimmed">{maskedApiKey}</Text>
                            <Tooltip label={clipboard.copied ? 'Скопировано' : 'Скопировать'}>
                              <ActionIcon
                                variant="subtle"
                                color={clipboard.copied ? 'teal' : 'gray'}
                                onClick={() => clipboard.copy(apiKey)}
                              >
                                {clipboard.copied ? <Check size={14} /> : <Copy size={14} />}
                              </ActionIcon>
                            </Tooltip>
                          </Group>
                        </Table.Td>
                        <Table.Td style={{ border: 'none' }}><Text size="xs" c="dimmed">2026-03-12</Text></Table.Td>
                        <Table.Td style={{ border: 'none' }} align="right">
                          <ActionIcon variant="subtle" color="red"><Trash2 size={16} /></ActionIcon>
                        </Table.Td>
                      </Table.Tr>
                    </Table.Tbody>
                  </Table>
                </Card>
              </Stack>
            </Tabs.Panel>

            <Tabs.Panel value="subscription">
              <Stack gap="xl">
                <Box>
                  <Title order={2} size="h3" mb={4}>Тариф и оплата</Title>
                  <Text c="dimmed" size="sm">Управляйте текущим тарифом, лимитами и платёжной информацией.</Text>
                </Box>

                <Card p="xl" radius="xl" bg="#f3f4f5">
                  <Group justify="space-between" align="flex-start" mb="xl" wrap="wrap" gap="lg">
                    <Box>
                      <Group gap="sm" mb={4}>
                        <Title order={3}>НеоФин.Документы Про</Title>
                        <Badge color="green" variant="light">АКТИВЕН</Badge>
                      </Group>
                      <Text size="sm" c="dimmed">Тариф обновится 12 апреля 2026 года.</Text>
                    </Box>
                    <Button variant="filled" bg="#00288e">Изменить тариф</Button>
                  </Group>

                  <Box mb="xl">
                    <Group justify="space-between" mb={8}>
                      <Text size="xs" fw={700} style={{ letterSpacing: '0.05em' }}>ЛИМИТ АНАЛИЗОВ</Text>
                      <Text size="xs" fw={700}>12 / 50</Text>
                    </Group>
                    <Progress value={24} size="sm" radius="xl" color="blue" />
                    <Text size="xs" c="dimmed" mt={8} ta="right">24% использовано в этом месяце</Text>
                  </Box>

                  <Box style={{ borderTop: '1px solid rgba(0,0,0,0.05)', paddingTop: 24 }}>
                    <Title order={4} size="h5" mb="md">Способ оплаты</Title>
                    <Card p="md" radius="md" bg="white">
                      <Group justify="space-between" wrap="wrap" gap="md">
                        <Group gap="md">
                          <CreditCard size={24} color="#00288e" />
                          <Box>
                            <Text fw={600} size="sm">•••• •••• •••• 4242</Text>
                            <Text size="xs" c="dimmed">Действует до 12/26</Text>
                          </Box>
                        </Group>
                        <Button variant="subtle" size="xs" color="red">Удалить карту</Button>
                      </Group>
                    </Card>
                  </Box>
                </Card>

                <Box>
                  <Title order={4} size="h5" mb="md">История платежей</Title>
                  <Card p={0} radius="xl" bg="#f3f4f5" style={{ overflow: 'hidden' }}>
                    <Table verticalSpacing="md" horizontalSpacing="xl">
                      <Table.Tbody>
                        <Table.Tr>
                          <Table.Td style={{ border: 'none' }}><Text size="sm">12 мар 2026</Text></Table.Td>
                          <Table.Td style={{ border: 'none' }}><Text size="sm" fw={600}>Тариф «Документы Про»</Text></Table.Td>
                          <Table.Td style={{ border: 'none' }}><Text size="sm">4 900 ₽</Text></Table.Td>
                          <Table.Td style={{ border: 'none' }} align="right">
                            <ActionIcon variant="subtle" color="gray"><Download size={16} /></ActionIcon>
                          </Table.Td>
                        </Table.Tr>
                      </Table.Tbody>
                    </Table>
                  </Card>
                </Box>
              </Stack>
            </Tabs.Panel>
          </Box>
        </SimpleGrid>
      </Tabs>
    </Stack>
  );
};
