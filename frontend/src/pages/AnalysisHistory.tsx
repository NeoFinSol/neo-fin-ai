import React from 'react';
import { Title, Text, Card, Table, Group, Badge, ThemeIcon, Stack, Button, Container, ActionIcon } from '@mantine/core';
import { FileText, Download, MoreVertical, FileCheck, Hourglass, XCircle } from 'lucide-react';

const mockHistory = [
  { id: '1', name: 'ООО "Альфа-Групп"', date: '20.03.2024', type: 'Годовой отчет', score: 85, status: 'completed' },
  { id: '2', name: 'ПАО "ТехноПром"', date: '18.03.2024', type: 'Квартальный Q4', score: 42, status: 'completed' },
  { id: '3', name: 'ИП Иванов И.И.', date: '15.03.2024', type: 'Налоговая декл.', score: 0, status: 'processing' },
  { id: '4', name: 'ЗАО "СтройИнвест"', date: '10.03.2024', type: 'Баланс 2023', score: 75, status: 'completed' },
  { id: '5', name: 'Global Logistics Ltd', date: '05.03.2024', type: 'Аудит', score: 0, status: 'failed' },
];

export const AnalysisHistory = () => {
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return (
          <Badge 
            variant="filled" 
            bg="#6cf8bb" 
            c="#00714d" 
            radius="xl" 
            size="sm" 
            fw={700}
            style={{ border: 'none' }}
            leftSection={<FileCheck size={12} />}
          >
            ГОТОВО
          </Badge>
        );
      case 'processing':
        return (
          <Badge 
            variant="filled" 
            bg="#e0e7ff" 
            c="#4338ca" 
            radius="xl" 
            size="sm" 
            fw={700}
            style={{ border: 'none' }}
            leftSection={<Hourglass size={12} />}
          >
            ОБРАБОТКА
          </Badge>
        );
      case 'failed':
        return (
          <Badge 
            variant="filled" 
            bg="#ffdad6" 
            c="#ba1a1a" 
            radius="xl" 
            size="sm" 
            fw={700}
            style={{ border: 'none' }}
            leftSection={<XCircle size={12} />}
          >
            ОШИБКА
          </Badge>
        );
      default:
        return <Badge radius="xl">НЕИЗВЕСТНО</Badge>;
    }
  };

  return (
    <Container size="xl" py="2rem">
      <Stack gap="xl">
        <Group justify="space-between" align="flex-end">
          <Stack gap={4}>
            <Title order={1} style={{ letterSpacing: '-0.02em', fontWeight: 800 }}>История анализов</Title>
            <Text c="dimmed" size="lg">Архив всех проведенных проверок и финансовых отчетов</Text>
          </Stack>
          <Group gap="md">
            <Button variant="subtle" leftSection={<Download size={18} />} color="gray">
              Скачать выбранные
            </Button>
            <Button variant="filled" bg="#ba1a1a">
              Удалить выбранные
            </Button>
          </Group>
        </Group>

        <Card padding={0} radius="md" shadow="sm" bg="white" style={{ border: 'none', overflow: 'hidden' }}>
          <Table verticalSpacing="md" horizontalSpacing="xl">
            <Table.Thead>
              <Table.Tr style={{ backgroundColor: '#f8f9fa' }}>
                <Table.Th style={{ border: 'none', color: '#6b7280', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Название компании</Table.Th>
                <Table.Th style={{ border: 'none', color: '#6b7280', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Дата</Table.Th>
                <Table.Th style={{ border: 'none', color: '#6b7280', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Тип отчета</Table.Th>
                <Table.Th style={{ border: 'none', color: '#6b7280', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Скоринг</Table.Th>
                <Table.Th style={{ border: 'none', color: '#6b7280', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Статус</Table.Th>
                <Table.Th style={{ border: 'none' }}></Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {mockHistory.map((item, index) => (
                <Table.Tr 
                  key={item.id} 
                  style={{ backgroundColor: index % 2 === 1 ? '#f3f4f5' : 'transparent' }}
                >
                  <Table.Td style={{ border: 'none' }}>
                    <Group gap="sm">
                      <ThemeIcon variant="light" color="red" size="md" radius="md">
                        <FileText size={18} />
                      </ThemeIcon>
                      <Text fw={600} size="sm">{item.name}</Text>
                    </Group>
                  </Table.Td>
                  <Table.Td style={{ border: 'none' }}>
                    <Text size="sm" c="dimmed">{item.date}</Text>
                  </Table.Td>
                  <Table.Td style={{ border: 'none' }}>
                    <Text size="sm">{item.type}</Text>
                  </Table.Td>
                  <Table.Td style={{ border: 'none' }}>
                    <Text 
                      fw={700} 
                      size="sm" 
                      style={{ fontFamily: 'JetBrains Mono' }}
                      c={item.status === 'completed' ? (item.score > 70 ? '#00714d' : item.score > 40 ? '#f59e0b' : '#ba1a1a') : 'dimmed'}
                    >
                      {item.status === 'completed' ? item.score : '--'}
                    </Text>
                  </Table.Td>
                  <Table.Td style={{ border: 'none' }}>
                    {getStatusBadge(item.status)}
                  </Table.Td>
                  <Table.Td style={{ border: 'none' }} align="right">
                    <Group gap="xs" justify="flex-end">
                      <ActionIcon variant="subtle" color="gray">
                        <Download size={16} />
                      </ActionIcon>
                      <ActionIcon variant="subtle" color="gray">
                        <MoreVertical size={16} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Card>
      </Stack>
    </Container>
  );
};
