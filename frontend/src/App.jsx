import {
  Badge,
  Button,
  Card,
  Container,
  Divider,
  Group,
  Loader,
  Paper,
  Progress,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { Dropzone, MIME_TYPES } from '@mantine/dropzone';
import { notifications } from '@mantine/notifications';
import { useEffect, useMemo, useRef, useState } from 'react';
import './App.css';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

const METRIC_LABELS = [
  { key: 'revenue', label: 'Выручка' },
  { key: 'net_profit', label: 'Чистая прибыль' },
  { key: 'total_assets', label: 'Активы (всего)' },
  { key: 'equity', label: 'Капитал' },
  { key: 'liabilities', label: 'Обязательства' },
  { key: 'current_assets', label: 'Оборотные активы' },
  { key: 'short_term_liabilities', label: 'Краткосрочные обязательства' },
  { key: 'accounts_receivable', label: 'Дебиторская задолженность' },
];

const formatNumber = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  return Number(value).toLocaleString('ru-RU', {
    maximumFractionDigits: 2,
  });
};

const statusMeta = (status) => {
  switch (status) {
    case 'uploading':
      return { label: 'Загрузка файла', color: 'blue' };
    case 'processing':
      return { label: 'Обработка', color: 'orange' };
    case 'completed':
      return { label: 'Готово', color: 'teal' };
    case 'failed':
      return { label: 'Ошибка', color: 'red' };
    default:
      return { label: 'Ожидание', color: 'gray' };
  }
};

const scoreColor = (score) => {
  if (score >= 80) return 'teal';
  if (score >= 60) return 'yellow';
  return 'red';
};

const riskLabel = (riskLevel) => {
  if (!riskLevel) return '—';
  return riskLevel[0].toUpperCase() + riskLevel.slice(1);
};

function App() {
  const [file, setFile] = useState(null);
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const pollingRef = useRef(null);

  const statusBadge = useMemo(() => statusMeta(status), [status]);

  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  const resetState = () => {
    setTaskId(null);
    setStatus('idle');
    setError(null);
    setResult(null);
  };

  const startPolling = (id) => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }

    pollingRef.current = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/result/${id}`);
        if (response.status === 404) {
          return;
        }
        if (!response.ok) {
          throw new Error(`Ошибка сервера: ${response.status}`);
        }

        const payload = await response.json();
        const payloadStatus = payload.status || 'processing';
        setStatus(payloadStatus);

        if (payloadStatus === 'completed') {
          setResult(payload.data || null);
          clearInterval(pollingRef.current);
        }

        if (payloadStatus === 'failed') {
          const message = payload.error || 'Не удалось обработать документ.';
          setError(message);
          clearInterval(pollingRef.current);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Ошибка сети.';
        setError(message);
        setStatus('failed');
        clearInterval(pollingRef.current);
      }
    }, 2000);
  };

  const handleUpload = async () => {
    if (!file) {
      notifications.show({
        color: 'red',
        title: 'Файл не выбран',
        message: 'Выберите PDF перед загрузкой.',
      });
      return;
    }

    setStatus('uploading');
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        let detail = 'Ошибка загрузки.';
        try {
          const payload = await response.json();
          detail = payload.detail || detail;
        } catch (err) {
          // ignore parse error
        }
        throw new Error(detail);
      }

      const payload = await response.json();
      const id = payload.task_id;
      setTaskId(id);
      setStatus('processing');
      notifications.show({
        color: 'teal',
        title: 'Файл принят',
        message: 'Запускаем анализ. Это может занять пару минут.',
      });
      startPolling(id);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Ошибка загрузки.';
      setError(message);
      setStatus('failed');
    }
  };

  const metricRows = (result?.metrics || {}) &&
    METRIC_LABELS.map((metric) => (
      <Table.Tr key={metric.key}>
        <Table.Td>{metric.label}</Table.Td>
        <Table.Td>{formatNumber(result?.metrics?.[metric.key])}</Table.Td>
      </Table.Tr>
    ));

  const ratioRows = result?.ratios
    ? Object.entries(result.ratios).map(([name, value]) => (
        <Table.Tr key={name}>
          <Table.Td>{name}</Table.Td>
          <Table.Td>{formatNumber(value)}</Table.Td>
        </Table.Tr>
      ))
    : [];

  const normalizedRows = result?.score?.details
    ? Object.entries(result.score.details).map(([name, value]) => (
        <Table.Tr key={name}>
          <Table.Td>{name}</Table.Td>
          <Table.Td>{formatNumber(value)}</Table.Td>
        </Table.Tr>
      ))
    : [];

  return (
    <Container size="lg" className="app-shell">
      <Paper radius="xl" className="hero" p="xl">
        <Stack gap="xs">
          <Title order={1} className="hero-title">
            НеоФин AI
          </Title>
          <Text className="hero-subtitle">
            ИИ-ассистент финансового директора для анализа отчетности и оценки риска.
          </Text>
          <Group gap="sm">
            <Badge variant="light" color="teal">PDF + OCR</Badge>
            <Badge variant="light" color="blue">Финансовые коэффициенты</Badge>
            <Badge variant="light" color="grape">NLP анализ</Badge>
          </Group>
        </Stack>
      </Paper>

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg" mt="xl">
        <Card radius="lg" className="card" withBorder>
          <Stack gap="md">
            <div>
              <Title order={3}>Загрузка отчета</Title>
              <Text size="sm" c="dimmed">
                Перетащите PDF или выберите файл вручную. После загрузки начнется
                анализ и расчет показателей.
              </Text>
            </div>
            <Dropzone
              onDrop={(files) => {
                setFile(files[0]);
                resetState();
              }}
              onReject={() => {
                notifications.show({
                  color: 'red',
                  title: 'Неверный формат',
                  message: 'Можно загрузить только PDF-файл.',
                });
              }}
              maxFiles={1}
              accept={[MIME_TYPES.pdf]}
              className="dropzone"
            >
              <Stack align="center" gap="xs">
                <Text fw={600}>Выберите PDF</Text>
                <Text size="sm" c="dimmed">
                  {file ? `Выбран файл: ${file.name}` : 'Файл пока не выбран'}
                </Text>
              </Stack>
            </Dropzone>
            <Group justify="space-between" wrap="nowrap">
              <Button
                size="md"
                radius="xl"
                onClick={handleUpload}
                disabled={status === 'uploading' || status === 'processing'}
              >
                Запустить анализ
              </Button>
              <Text size="sm" c="dimmed">
                {file ? `${(file.size / (1024 * 1024)).toFixed(2)} MB` : '—'}
              </Text>
            </Group>
          </Stack>
        </Card>

        <Card radius="lg" className="card" withBorder>
          <Stack gap="md">
            <Group justify="space-between">
              <Title order={3}>Статус</Title>
              <Badge color={statusBadge.color} variant="light">
                {statusBadge.label}
              </Badge>
            </Group>
            <Text size="sm" c="dimmed">
              {status === 'idle' && 'Готовы принять файл для анализа.'}
              {status === 'uploading' && 'Загружаем файл на сервер.'}
              {status === 'processing' && 'Извлекаем текст, таблицы и рассчитываем показатели.'}
              {status === 'completed' && 'Анализ завершен. Ниже доступен отчет.'}
              {status === 'failed' && 'Произошла ошибка. Проверьте файл и попробуйте еще раз.'}
            </Text>
            {status === 'processing' && (
              <Group gap="sm">
                <Loader size="sm" />
                <Text size="sm">Идет обработка...</Text>
              </Group>
            )}
            {taskId && (
              <Text size="xs" c="dimmed">
                Task ID: {taskId}
              </Text>
            )}
            {error && (
              <Text size="sm" c="red">
                {error}
              </Text>
            )}
          </Stack>
        </Card>
      </SimpleGrid>

      {result && (
        <Stack gap="lg" mt="xl">
          <Card radius="lg" className="card" withBorder>
            <Group justify="space-between" align="center">
              <Title order={3}>Интегральный скоринг</Title>
              <Badge color={scoreColor(result?.score?.score || 0)} variant="light">
                Риск: {riskLabel(result?.score?.risk_level)}
              </Badge>
            </Group>
            <Divider my="md" />
            <Stack gap="sm">
              <Group justify="space-between">
                <Text fw={600}>Итоговый балл</Text>
                <Text fw={600}>{formatNumber(result?.score?.score)}</Text>
              </Group>
              <Progress
                value={Number(result?.score?.score || 0)}
                color={scoreColor(result?.score?.score || 0)}
                size="lg"
                radius="xl"
              />
              {normalizedRows.length > 0 && (
                <Table highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Коэффициент</Table.Th>
                      <Table.Th>Норм. оценка</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>{normalizedRows}</Table.Tbody>
                </Table>
              )}
            </Stack>
          </Card>

          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg">
            <Card radius="lg" className="card" withBorder>
              <Title order={3}>Финансовые показатели</Title>
              <Divider my="md" />
              <Table>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Показатель</Table.Th>
                    <Table.Th>Значение</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>{metricRows}</Table.Tbody>
              </Table>
            </Card>

            <Card radius="lg" className="card" withBorder>
              <Title order={3}>Коэффициенты</Title>
              <Divider my="md" />
              {ratioRows.length > 0 ? (
                <Table>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Коэффициент</Table.Th>
                      <Table.Th>Значение</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>{ratioRows}</Table.Tbody>
                </Table>
              ) : (
                <Text size="sm" c="dimmed">
                  Коэффициенты пока не рассчитаны.
                </Text>
              )}
            </Card>
          </SimpleGrid>

          <SimpleGrid cols={{ base: 1, md: 3 }} spacing="lg">
            <Card radius="lg" className="card" withBorder>
              <Title order={4}>Риски</Title>
              <Divider my="sm" />
              {result?.narrative?.risks?.length ? (
                <Stack gap="xs">
                  {result.narrative.risks.map((risk) => (
                    <Text key={risk} size="sm">
                      • {risk}
                    </Text>
                  ))}
                </Stack>
              ) : (
                <Text size="sm" c="dimmed">
                  Нет данных.
                </Text>
              )}
            </Card>

            <Card radius="lg" className="card" withBorder>
              <Title order={4}>Ключевые факторы</Title>
              <Divider my="sm" />
              {result?.narrative?.key_factors?.length ? (
                <Stack gap="xs">
                  {result.narrative.key_factors.map((factor) => (
                    <Text key={factor} size="sm">
                      • {factor}
                    </Text>
                  ))}
                </Stack>
              ) : (
                <Text size="sm" c="dimmed">
                  Нет данных.
                </Text>
              )}
            </Card>

            <Card radius="lg" className="card" withBorder>
              <Title order={4}>Рекомендации</Title>
              <Divider my="sm" />
              {result?.narrative?.recommendations?.length ? (
                <Stack gap="xs">
                  {result.narrative.recommendations.map((rec) => (
                    <Text key={rec} size="sm">
                      • {rec}
                    </Text>
                  ))}
                </Stack>
              ) : (
                <Text size="sm" c="dimmed">
                  Нет данных.
                </Text>
              )}
            </Card>
          </SimpleGrid>

          <Card radius="lg" className="card" withBorder>
            <Group justify="space-between">
              <Title order={4}>Дополнительные детали</Title>
              <Badge variant="light" color={result?.scanned ? 'orange' : 'teal'}>
                {result?.scanned ? 'PDF скан' : 'PDF с текстом'}
              </Badge>
            </Group>
            <Divider my="md" />
            <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
              <Paper className="stat" withBorder>
                <Text size="xs" c="dimmed">Таблиц найдено</Text>
                <Text fw={600}>{result?.tables?.length ?? 0}</Text>
              </Paper>
              <Paper className="stat" withBorder>
                <Text size="xs" c="dimmed">Длина текста</Text>
                <Text fw={600}>{result?.text ? result.text.length : 0}</Text>
              </Paper>
              <Paper className="stat" withBorder>
                <Text size="xs" c="dimmed">OCR</Text>
                <Text fw={600}>{result?.scanned ? 'Да' : 'Нет'}</Text>
              </Paper>
            </SimpleGrid>
          </Card>
        </Stack>
      )}
    </Container>
  );
}

export default App;
