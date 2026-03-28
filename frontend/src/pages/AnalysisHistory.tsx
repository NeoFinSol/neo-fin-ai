import React, { useState, useEffect, useCallback } from 'react';
import {
  Title, Text, Card, Table, Group, Badge, ThemeIcon, Stack, Button,
  Container, ActionIcon, ScrollArea, Anchor, Skeleton, Pagination, Alert,
} from '@mantine/core';
import { FileText, FileCheck, Hourglass, XCircle, Eye, AlertCircle, RefreshCw } from 'lucide-react';
import { DetailedReport } from './DetailedReport';
import { apiClient } from '../api/client';
import { AnalysisSummary, AnalysisListResponse, AnalysisData } from '../api/interfaces';

const PAGE_SIZE = 20;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function formatDate(isoDate: string): string {
  const d = new Date(isoDate);
  const day = String(d.getUTCDate()).padStart(2, '0');
  const month = String(d.getUTCMonth() + 1).padStart(2, '0');
  const year = d.getUTCFullYear();
  return `${day}.${month}.${year}`;
}

function getStatusBadge(riskLevel: string | null) {
  const labels: Record<string, { bg: string; c: string; label: string; icon: React.ReactNode }> = {
    low: { bg: '#6cf8bb', c: '#00714d', label: 'НИЗКИЙ', icon: <FileCheck size={12} /> },
    medium: { bg: '#fef3c7', c: '#f59e0b', label: 'СРЕДНИЙ', icon: <Hourglass size={12} /> },
    high: { bg: '#ffdad6', c: '#ba1a1a', label: 'ВЫСОКИЙ', icon: <XCircle size={12} /> },
    critical: { bg: '#ffd7d7', c: '#8b0000', label: 'КРИТИЧЕСКИЙ', icon: <AlertCircle size={12} /> },
  };
  const cfg = riskLevel ? (labels[riskLevel] ?? labels.medium) : labels.medium;
  return (
    <Badge variant="filled" bg={cfg.bg} c={cfg.c} radius="xl" size="sm" fw={700}
      style={{ border: 'none' }} leftSection={cfg.icon}>
      {cfg.label}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const AnalysisHistory = () => {
  const [items, setItems] = useState<AnalysisSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Detail view state
  const [detailData, setDetailData] = useState<AnalysisData | null>(null);
  const [detailFilename, setDetailFilename] = useState<string | undefined>(undefined);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchList = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.get<AnalysisListResponse>(
        `/analyses?page=${p}&page_size=${PAGE_SIZE}`
      );
      setItems(res.data.items);
      setTotal(res.data.total);
    } catch (e: unknown) {
      const axiosErr = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(axiosErr?.response?.data?.detail ?? axiosErr?.message ?? 'Ошибка загрузки истории');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchList(page);
  }, [page, fetchList]);

  const handleRowClick = async (item: AnalysisSummary) => {
    setDetailLoading(true);
    try {
      const res = await apiClient.get<{ task_id: string; status: string; created_at: string; data: AnalysisData | null }>(
        `/analyses/${item.task_id}`
      );
      if (res.data.data) {
        setDetailData(res.data.data);
        setDetailFilename(item.filename ?? undefined);
      } else {
        setError('Данные анализа недоступны — возможно, обработка ещё не завершена.');
      }
    } catch (e: unknown) {
      const axiosErr = e as { response?: { data?: { detail?: string } } };
      setError(axiosErr?.response?.data?.detail ?? 'Не удалось загрузить детали анализа.');
    } finally {
      setDetailLoading(false);
    }
  };

  // --- Detail view ---
  if (detailData) {
    return (
      <Stack gap="md">
        <Button variant="subtle" onClick={() => setDetailData(null)} style={{ alignSelf: 'flex-start' }}>
          ← Назад к истории
        </Button>
        <DetailedReport result={detailData} filename={detailFilename} />
      </Stack>
    );
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <Container size="xl" py="2rem">
      <Stack gap="xl">
        {/* Header */}
        <Stack gap={4}>
          <Title order={1} style={{ letterSpacing: '-0.02em', fontWeight: 800 }}>История анализов</Title>
          <Text c="dimmed" size="lg">
            {!loading && total === 0 && !error
              ? 'Пока нет проведённых анализов. Загрузите PDF на вкладке Dashboard.'
              : `Всего анализов: ${total}`}
          </Text>
        </Stack>

        {/* Error state */}
        {error && (
          <Alert icon={<AlertCircle size={16} />} color="red" title="Ошибка загрузки">
            {error}
            <Button
              variant="subtle"
              color="red"
              size="xs"
              mt="xs"
              leftSection={<RefreshCw size={14} />}
              onClick={() => fetchList(page)}
            >
              Повторить
            </Button>
          </Alert>
        )}

        {/* Skeleton while loading */}
        {loading && (
          <Stack gap="sm">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} height={48} radius="md" />
            ))}
          </Stack>
        )}

        {/* Table */}
        {!loading && !error && items.length > 0 && (
          <Card padding={0} radius="md" shadow="sm" bg="white" style={{ border: 'none', overflow: 'hidden' }}>
            <ScrollArea>
              <Table verticalSpacing="md" horizontalSpacing="xl">
                <Table.Thead>
                  <Table.Tr style={{ backgroundColor: '#f8f9fa' }}>
                    {['Файл', 'Дата', 'Скоринг', 'Риск', ''].map((h, i) => (
                      <Table.Th key={i} style={{ border: 'none', color: '#6b7280', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        {h}
                      </Table.Th>
                    ))}
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {items.map((item, index) => (
                    <Table.Tr
                      key={item.task_id}
                      style={{ backgroundColor: index % 2 === 1 ? '#f3f4f5' : 'transparent', cursor: 'pointer' }}
                      onClick={() => handleRowClick(item)}
                    >
                      <Table.Td style={{ border: 'none' }}>
                        <Group gap="sm">
                          <ThemeIcon variant="light" color="blue" size="md" radius="md">
                            <FileText size={18} />
                          </ThemeIcon>
                          <Anchor size="sm" fw={600} underline="hover">
                            {item.filename ?? '—'}
                          </Anchor>
                        </Group>
                      </Table.Td>
                      <Table.Td style={{ border: 'none' }}>
                        <Text size="sm" c="dimmed">{formatDate(item.created_at)}</Text>
                      </Table.Td>
                      <Table.Td style={{ border: 'none' }}>
                        <Text fw={700} size="sm" style={{ fontFamily: 'JetBrains Mono' }}>
                          {item.score != null ? item.score.toFixed(1) : '—'}
                        </Text>
                      </Table.Td>
                      <Table.Td style={{ border: 'none' }}>
                        {item.risk_level != null ? getStatusBadge(item.risk_level) : <Text size="sm">—</Text>}
                      </Table.Td>
                      <Table.Td style={{ border: 'none' }} align="right">
                        <ActionIcon
                          variant="subtle"
                          color="blue"
                          loading={detailLoading}
                          onClick={(e) => { e.stopPropagation(); handleRowClick(item); }}
                        >
                          <Eye size={16} />
                        </ActionIcon>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </ScrollArea>
          </Card>
        )}

        {/* Pagination */}
        {!loading && totalPages > 1 && (
          <Group justify="center">
            <Pagination total={totalPages} value={page} onChange={setPage} />
          </Group>
        )}
      </Stack>
    </Container>
  );
};
