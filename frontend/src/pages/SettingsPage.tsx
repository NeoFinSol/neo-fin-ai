import React, { useState } from 'react';
import { 
  Title, 
  Text, 
  Card, 
  Stack, 
  Group, 
  Switch, 
  TextInput, 
  Button, 
  ThemeIcon, 
  Tabs, 
  Box, 
  Avatar, 
  ActionIcon, 
  Tooltip, 
  useMantineColorScheme, 
  Badge, 
  Table, 
  Progress 
} from '@mantine/core';
import { 
  User, 
  Shield, 
  Key, 
  CreditCard, 
  Copy, 
  Check, 
  Moon, 
  Sun, 
  Plus, 
  Trash2, 
  Download 
} from 'lucide-react';
import { useClipboard } from '@mantine/hooks';

export const SettingsPage = () => {
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();
  const clipboard = useClipboard({ timeout: 2000 });

  // Get API key from environment or use placeholder
  const apiKey = import.meta.env.VITE_API_KEY || '****-****-****-****-****';
  const maskedApiKey = apiKey.length > 20 ? `${apiKey.substring(0, 4)}...${apiKey.substring(apiKey.length - 4)}` : apiKey;

  return (
    <Box>
      <header style={{ marginBottom: 40 }}>
        <Title order={1} style={{ letterSpacing: '-0.02em', fontWeight: 800 }}>Настройки</Title>
        <Text c="dimmed" size="lg">Управление профилем и параметрами системы NeoFin AI</Text>
      </header>

      <Tabs defaultValue="profile" orientation="vertical" variant="pills" radius="md" 
        classNames={{
          root: 'gap-10',
          list: 'w-[240px] border-none',
          tab: 'px-4 py-3 font-semibold data-[active]:bg-[#f3f4f5] data-[active]:text-[#00288e]',
          panel: 'flex-1'
        }}
      >
        <Tabs.List>
          <Tabs.Tab value="profile" leftSection={<User size={18} />}>Профиль</Tabs.Tab>
          <Tabs.Tab value="security" leftSection={<Shield size={18} />}>Безопасность</Tabs.Tab>
          <Tabs.Tab value="api" leftSection={<Key size={18} />}>API Ключи</Tabs.Tab>
          <Tabs.Tab value="subscription" leftSection={<CreditCard size={18} />}>Подписка</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="profile">
          <Stack gap="xl">
            <Box>
              <Title order={2} size="h3" mb={4}>Профиль</Title>
              <Text c="dimmed" size="sm" mb="xl">Обновите вашу личную информацию и фото профиля.</Text>
            </Box>

            <Card p="xl" radius="md" bg="#f3f4f5" style={{ border: 'none' }}>
              <Group gap="xl" align="flex-start">
                <Stack align="center" gap="xs">
                  <Avatar 
                    src="https://raw.githubusercontent.com/mantinedev/mantine/master/.demo/avatars/avatar-1.png" 
                    size={100} 
                    radius="md" 
                  />
                  <Button variant="subtle" size="xs">Изменить</Button>
                </Stack>
                
                <Stack gap="md" style={{ flex: 1 }}>
                  <Group grow>
                    <TextInput label="ИМЯ" placeholder="Александр" defaultValue="Александр" styles={inputStyles} />
                    <TextInput label="ФАМИЛИЯ" placeholder="Иванов" defaultValue="Иванов" styles={inputStyles} />
                  </Group>
                  <TextInput label="EMAIL" placeholder="alexander.i@neofin.ai" defaultValue="alexander.i@neofin.ai" styles={inputStyles} />
                  <Group grow>
                    <TextInput label="КОМПАНИЯ" placeholder="NeoFin AI" defaultValue="NeoFin AI" styles={inputStyles} />
                    <TextInput label="ДОЛЖНОСТЬ" placeholder="Lead Analyst" defaultValue="Lead Analyst" styles={inputStyles} />
                  </Group>
                  <Button 
                    variant="filled" 
                    bg="#00288e" 
                    style={{ alignSelf: 'flex-start' }}
                    className="hover:shadow-md"
                  >
                    Сохранить изменения
                  </Button>
                </Stack>
              </Group>
            </Card>

            <Card p="xl" radius="md" bg="#f3f4f5" style={{ border: 'none' }}>
              <Title order={4} mb="md">Внешний вид</Title>
              <Group justify="space-between">
                <Box>
                  <Text fw={600}>Темная тема</Text>
                  <Text size="xs" c="dimmed">Использовать Obsidian Slate для интерфейса</Text>
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
              <Text c="dimmed" size="sm" mb="xl">Управляйте паролями и защитой аккаунта.</Text>
            </Box>

            <Card p="xl" radius="md" bg="#f3f4f5" style={{ border: 'none' }}>
              <Stack gap="md">
                <TextInput label="ТЕКУЩИЙ ПАРОЛЬ" type="password" placeholder="••••••••" styles={inputStyles} />
                <Group grow>
                  <TextInput label="НОВЫЙ ПАРОЛЬ" type="password" placeholder="••••••••" styles={inputStyles} />
                  <TextInput label="ПОДТВЕРЖДЕНИЕ" type="password" placeholder="••••••••" styles={inputStyles} />
                </Group>
                <Button variant="filled" bg="#00288e" style={{ alignSelf: 'flex-start' }}>Обновить пароль</Button>
              </Stack>
            </Card>

            <Card p="xl" radius="md" bg="#f3f4f5" style={{ border: 'none' }}>
              <Group justify="space-between">
                <Box>
                  <Text fw={600}>Двухфакторная аутентификация</Text>
                  <Text size="xs" c="dimmed">Добавьте дополнительный уровень защиты вашему аккаунту.</Text>
                </Box>
                <Switch size="md" color="blue" defaultChecked />
              </Group>
            </Card>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="api">
          <Stack gap="xl">
            <Group justify="space-between">
              <Box>
                <Title order={2} size="h3" mb={4}>API ключи</Title>
                <Text c="dimmed" size="sm">Управляйте доступом для ваших интеграций.</Text>
              </Box>
              <Button variant="light" leftSection={<Plus size={18} />}>Создать новый ключ</Button>
            </Group>

            <Card p={0} radius="md" bg="#f3f4f5" style={{ border: 'none', overflow: 'hidden' }}>
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
                    <Table.Td style={{ border: 'none' }}><Text fw={600} size="sm">Production Alpha</Text></Table.Td>
                    <Table.Td style={{ border: 'none' }}>
                       <Group gap="xs">
                         <Text size="xs" ff="JetBrains Mono" c="dimmed">{maskedApiKey}</Text>
                         <Tooltip label={clipboard.copied ? 'Скопировано!' : 'Копировать'}>
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
                    <Table.Td style={{ border: 'none' }}><Text size="xs" c="dimmed">2024-03-12</Text></Table.Td>
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
              <Title order={2} size="h3" mb={4}>Тариф и Оплата</Title>
              <Text c="dimmed" size="sm" mb="xl">Управляйте вашим тарифным планом и способами оплаты.</Text>
            </Box>

            <Card p="xl" radius="md" bg="#f3f4f5" style={{ border: 'none' }}>
              <Group justify="space-between" align="flex-start" mb="xl">
                <Box>
                  <Group gap="sm" mb={4}>
                    <Title order={3}>NeoFin Pro</Title>
                    <Badge color="green" variant="light">ACTIVE</Badge>
                  </Group>
                  <Text size="sm" c="dimmed">Ваш тарифный план обновляется 12 апреля 2024 года.</Text>
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
                <Card p="md" radius="md" bg="white" style={{ border: 'none' }}>
                  <Group justify="space-between">
                    <Group gap="md">
                      <CreditCard size={24} color="#00288e" />
                      <Box>
                        <Text fw={600} size="sm">•••• •••• •••• 4242</Text>
                        <Text size="xs" c="dimmed">Expires 12/26</Text>
                      </Box>
                    </Group>
                    <Button variant="subtle" size="xs" color="red">Удалить карту</Button>
                  </Group>
                </Card>
              </Box>
            </Card>

            <Box>
              <Title order={4} size="h5" mb="md">История платежей</Title>
              <Card p={0} radius="md" bg="#f3f4f5" style={{ border: 'none', overflow: 'hidden' }}>
                <Table verticalSpacing="md" horizontalSpacing="xl">
                  <Table.Tbody>
                    <Table.Tr>
                      <Table.Td style={{ border: 'none' }}><Text size="sm">Мар 12, 2024</Text></Table.Td>
                      <Table.Td style={{ border: 'none' }}><Text size="sm" fw={600}>Pro Monthly Plan</Text></Table.Td>
                      <Table.Td style={{ border: 'none' }}><Text size="sm">$49.00</Text></Table.Td>
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
      </Tabs>
    </Box>
  );
};

const inputStyles = {
  label: { fontSize: 10, fontWeight: 700, letterSpacing: '0.05em', marginBottom: 8, color: '#6b7280' },
  input: { backgroundColor: 'white', border: 'none', height: 44, fontSize: 14 }
};
