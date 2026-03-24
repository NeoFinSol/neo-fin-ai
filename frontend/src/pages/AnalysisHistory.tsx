import React, { useState } from 'react';
import {
  Title, Text, Card, Table, Group, Badge, ThemeIcon, Stack, Button,
  Container, ActionIcon, ScrollArea, Anchor,
} from '@mantine/core';
import {
  FileText, Download, MoreVertical, FileCheck, Hourglass, XCircle, Eye, Trash2,
} from 'lucide-react';
import { DetailedReport } from './DetailedReport';
import { useHistory, HistoryEntry } from '../context/AnalysisHistoryContext';

export const AnalysisHistory = () => {
  const { history, removeEntry, clearHistory } = useHistory();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selectedEntry = selectedId ? history.find((e) => e.id === selectedId) : null;

  const getStatusBadge = (status: string) => {
    const labels: Record<string, { bg: string; c: string; label: string; icon: React.ReactNode }> = {
      low: { bg: '#6cf8bb', c: '#00714d', label: 'НИЗКИЙ', icon: <FileCheck size={12} /> },
      medium: { bg: '#fef3c7', c: '#f59e0b', label: 'СРЕДНИЙ', icon: <Hourglass size={12} /> },
      high: { bg: '#ffdad6', c: '#ba1a1a', label: 'ВЫСОКИЙ', icon: <XCircle size={12} /> },
    };
    const cfg = labels[status] || labels.medium;
    return (
      <Badge variant="filled" bg={cfg.bg} c={cfg.c} radius="xl" size="sm" fw={700}
        style={{ border: 'none' }} leftSection={cfg.icon}>
        {cfg.label}
      </Badge>
    );
  };

  if (selectedEntry) {
    return (
      <Stack gap="md">
        <Button variant="subtle" onClick={() => setSelectedId(null)} style={{ alignSelf: 'flex-start' }}>
          ← Назад к истории
        </Button>
        <DetailedReport result={selectedEntry.result} filename={selectedEntry.filename} />
      </Stack>
    );
  }

  return (
    <Container size="xl" py="2rem">
      <Stack gap="xl">
        <Group justify="space-between" align="flex-end">
          <Stack gap={4}>
            <Title order={1} style={{ letterSpacing: '-0.02em', fontWeight: 800 }}>История анализов</Title>
            <Text c="dimmed" size="lg">
              {history.length === 0
                ? 'Пока нет проведённых анализов. Загрузите PDF на вкладке Dashboard.'
                : `Всего анализов: ${history.length}`}
            </Text>
          </Stack>
          {history.length > 0 && (
            <Button variant="light" color="red" onClick={clearHistory}>
              Очистить историю
            </Button>
          )}
        </Group>

        {history.length > 0 && (
          <Card padding={0} radius="md" shadow="sm" bg="white" style={{ border: 'none', overflow: 'hidden' }}>
            <ScrollArea>
              <Table verticalSpacing="md" horizontalSpacing="xl">
                <Table.Thead>
                  <Table.Tr style={{ backgroundColor: '#f8f9fa' }}>
                    <Table.Th style={{ border: 'none', color: '#6b7280', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Файл</Table.Th>
                    <Table.Th style={{ border: 'none', color: '#6b7280', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Дата</Table.Th>
                    <Table.Th style={{ border: 'none', color: '#6b7280', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Скоринг</Table.Th>
                    <Table.Th style={{ border: 'none', color: '#6b7280', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Риск</Table.Th>
                    <Table.Th style={{ border: 'none' }}></Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {history.map((item, index) => (
                    <Table.Tr
                      key={item.id}
                      style={{
                        backgroundColor: index % 2 === 1 ? '#f3f4f5' : 'transparent',
                        cursor: 'pointer',
                      }}
                      onClick={() => setSelectedId(item.id)}
                    >
                      <Table.Td style={{ border: 'none' }}>
                        <Group gap="sm">
                          <ThemeIcon variant="light" color="blue" size="md" radius="md">
                            <FileText size={18} />
                          </ThemeIcon>
                          <Anchor size="sm" fw={600} underline="hover">
                            {item.filename}
                          </Anchor>
                        </Group>
                      </Table.Td>
                      <Table.Td style={{ border: 'none' }}>
                        <Text size="sm" c="dimmed">{item.date}</Text>
                      </Table.Td>
                      <Table.Td style={{ border: 'none' }}>
                        <Text fw={700} size="sm" style={{ fontFamily: 'JetBrains Mono' }}>
                          {item.score.toFixed(1)}
                        </Text>
                      </Table.Td>
                      <Table.Td style={{ border: 'none' }}>
                        {getStatusBadge(item.riskLevel)}
                      </Table.Td>
                      <Table.Td style={{ border: 'none' }} align="right" onClick={(e) => e.stopPropagation()}>
                        <Group gap="xs" justify="flex-end">
                          <ActionIcon variant="subtle" color="blue" onClick={() => setSelectedId(item.id)}>
                            <Eye size={16} />
                          </ActionIcon>
                          <ActionIcon variant="subtle" color="red" onClick={() => removeEntry(item.id)}>
                            <Trash2 size={16} />
                          </ActionIcon>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </ScrollArea>
          </Card>
        )}
      </Stack>
    </Container>
  );
};
