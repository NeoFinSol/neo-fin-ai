import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Group,
  Paper,
  Progress,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Timeline,
  Title,
} from '@mantine/core';
import { Dropzone, FileRejection } from '@mantine/dropzone';
import {
  IconAlertCircle,
  IconBrain,
  IconChartBar,
  IconFileAnalytics,
  IconFileText,
  IconLoader,
  IconUpload,
  IconX,
} from '@tabler/icons-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { apiClient } from '../api/client';
import { AIProvider, AIProvidersResponse } from '../api/interfaces';
import { AiProviderMenu } from '../components/upload/AiProviderMenu';
import { useAnalysis } from '../context/AnalysisContext';
import { useHistory } from '../context/AnalysisHistoryContext';
import { ECOSYSTEM_NAME, PRODUCT_DESCRIPTION, PRODUCT_NAME, PRODUCT_TAGLINE } from '../constants/branding';
import { DetailedReport } from './DetailedReport';

export function Dashboard() {
  const { status, result, filename, error, analyze, reset } = useAnalysis();
  const { addEntry } = useHistory();
  const savedRef = useRef(false);
  const [selectedProvider, setSelectedProvider] = useState<AIProvider>('auto');
  const [providerOptions, setProviderOptions] = useState<AIProvider[]>(['auto']);

  const isPending = status === 'uploading' || status === 'processing';

  const handleUpload = useCallback((files: File[]) => {
    if (files.length > 0) {
      savedRef.current = false;
      analyze(files[0], selectedProvider);
    }
  }, [analyze, selectedProvider]);

  useEffect(() => {
    if (result && filename && !savedRef.current) {
      addEntry(filename, result);
      savedRef.current = true;
    }
  }, [result, filename, addEntry]);

  useEffect(() => {
    let active = true;

    const loadProviders = async () => {
      try {
        const response = await apiClient.get<AIProvidersResponse>('/system/ai/providers');
        if (!active) {
          return;
        }

        const nextOptions: AIProvider[] = response.data.available_providers.length > 0
          ? response.data.available_providers
          : ['auto'];
        const fallbackProvider = response.data.default_provider && nextOptions.includes(response.data.default_provider)
          ? response.data.default_provider
          : 'auto';
        const preferredProvider: AIProvider = nextOptions.includes('ollama')
          ? 'ollama'
          : fallbackProvider;

        setProviderOptions(nextOptions);
        setSelectedProvider((current) => {
          if (current !== 'auto' && nextOptions.includes(current)) {
            return current;
          }
          return preferredProvider;
        });
      } catch {
        if (!active) {
          return;
        }
        setProviderOptions(['auto']);
      }
    };

    void loadProviders();

    return () => {
      active = false;
    };
  }, []);

  const handleReject = useCallback((rejections: FileRejection[]) => {
    console.warn('File rejected:', rejections[0]?.errors[0]?.message);
  }, []);

  const progressStepNum = status === 'uploading' ? 0
    : status === 'processing' ? 2
      : status === 'completed' ? 4
        : 0;

  const statusText = status === 'uploading' ? 'Загрузка...' : 'Анализ документа...';

  if (result) {
    return (
      <Stack gap="md">
        <DetailedReport result={result} filename={filename} />
        <Button
          variant="light"
          onClick={() => { reset(); savedRef.current = false; }}
          style={{ alignSelf: 'center' }}
        >
          Новый анализ
        </Button>
      </Stack>
    );
  }

  return (
    <Stack gap="xl">
      <Paper
        radius="xl"
        p={{ base: 'xl', md: '2rem' }}
        style={{
          background: 'linear-gradient(145deg, rgba(0, 40, 142, 0.06), rgba(255, 255, 255, 0.98))',
          border: '1px solid rgba(0, 40, 142, 0.08)',
        }}
      >
        <Stack align="center" gap="sm" ta="center">
          <Badge variant="light" color="blue" radius="xl">
            Модуль экосистемы {ECOSYSTEM_NAME}
          </Badge>
          <Title order={1} size="h1" style={{ letterSpacing: '-0.03em' }}>
            {PRODUCT_NAME}
          </Title>
          <Text c="dimmed" size="lg" maw={760}>
            {PRODUCT_TAGLINE}
          </Text>
          <Text size="sm" c="dimmed" maw={820}>
            Загружайте PDF-отчёты, получайте детерминированный скоринг, финансовые коэффициенты и AI-пояснения без ручной рутины.
          </Text>
        </Stack>
      </Paper>

      {error && (
        <Alert
          icon={<IconAlertCircle size="1rem" />}
          title="Ошибка"
          color="red"
          variant="filled"
          withCloseButton
          onClose={reset}
        >
          {error}
        </Alert>
      )}

      <Card
        shadow="sm"
        padding="xl"
        radius="xl"
        withBorder={!isPending}
        style={{
          overflow: 'hidden',
          background: isPending ? 'white' : 'linear-gradient(180deg, rgba(255,255,255,1), rgba(247,248,252,1))',
        }}
      >
        {isPending ? (
          <Stack align="center" gap="lg" py="xl">
            <ThemeIcon size={60} radius="xl" color="blue" variant="light">
              {progressStepNum === 0 ? <IconUpload size={30} stroke={1.5} /> : <IconBrain size={30} stroke={1.5} />}
            </ThemeIcon>

            <Box w="100%">
              <Group justify="space-between" mb={5}>
                <Text size="sm" fw={500}>{statusText}</Text>
                {progressStepNum < 4 && <IconLoader size={16} className="animate-spin" />}
              </Group>
              <Progress value={100} animated size="sm" radius="xl" color="blue" />
            </Box>

            <Timeline active={progressStepNum} bulletSize={24} lineWidth={2} mt="md">
              <Timeline.Item bullet={<IconUpload size={12} />} title="Загрузка">
                <Text c="dimmed" size="xs">Отправка файла</Text>
              </Timeline.Item>
              <Timeline.Item bullet={<IconFileText size={12} />} title="Извлечение данных">
                <Text c="dimmed" size="xs">OCR, парсинг таблиц</Text>
              </Timeline.Item>
              <Timeline.Item bullet={<IconChartBar size={12} />} title="Расчёт показателей">
                <Text c="dimmed" size="xs">Ликвидность, рентабельность</Text>
              </Timeline.Item>
              <Timeline.Item bullet={<IconBrain size={12} />} title="ИИ-анализ">
                <Text c="dimmed" size="xs">Риски и рекомендации</Text>
              </Timeline.Item>
            </Timeline>

            <Text size="xs" c="dimmed" ta="center">
              Обработка может занять от 30 секунд до 5 минут
            </Text>

            <Button
              variant="subtle"
              color="gray"
              size="xs"
              onClick={() => { reset(); savedRef.current = false; }}
            >
              Отменить и начать заново
            </Button>
          </Stack>
        ) : (
          <Stack gap="lg">
            <Group justify="space-between" align="flex-start">
              <Box>
                <Text fw={700} size="lg">Загрузка отчёта</Text>
                <Text size="sm" c="dimmed" maw={560}>
                  Переключатель влияет на AI-контур анализа, но не меняет детерминированный скоринг.
                </Text>
              </Box>
              <AiProviderMenu
                value={selectedProvider}
                options={providerOptions}
                onChange={setSelectedProvider}
                disabled={isPending}
              />
            </Group>

            <Dropzone
              onDrop={handleUpload}
              onReject={handleReject}
              maxSize={50 * 1024 * 1024}
              accept={{ 'application/pdf': ['.pdf'] }}
              multiple={false}
              styles={{
                root: {
                  borderStyle: 'dashed',
                  borderWidth: 2,
                  borderColor: 'rgba(0, 40, 142, 0.16)',
                  background: 'linear-gradient(180deg, rgba(0, 40, 142, 0.02), rgba(255,255,255,0.96))',
                  padding: '3rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  borderRadius: 20,
                },
              }}
            >
              <Group justify="center" gap="xl" mih={180} style={{ pointerEvents: 'none' }}>
                <Dropzone.Accept>
                  <IconUpload size={52} color="var(--mantine-color-blue-6)" stroke={1.5} />
                </Dropzone.Accept>
                <Dropzone.Reject>
                  <IconX size={52} color="var(--mantine-color-red-6)" stroke={1.5} />
                </Dropzone.Reject>
                <Dropzone.Idle>
                  <IconFileAnalytics size={52} color="var(--mantine-color-gray-6)" stroke={1.5} />
                </Dropzone.Idle>

                <Box>
                  <Text size="xl" inline fw={700}>Перетащите PDF-отчёт сюда</Text>
                  <Text size="sm" c="dimmed" mt={7}>или нажмите для выбора файла</Text>
                  <Text size="xs" c="dimmed" mt={12}>Формат: PDF (до 50 МБ)</Text>
                </Box>
              </Group>
            </Dropzone>
          </Stack>
        )}
      </Card>

      <SimpleGrid cols={{ base: 1, md: 3 }} spacing="lg">
        <Card radius="xl">
          <Text size="xs" fw={700} c="dimmed" tt="uppercase">Документы</Text>
          <Text fw={700} size="lg" mt={6}>PDF без ручной разметки</Text>
          <Text size="sm" c="dimmed" mt="sm">
            Сервис извлекает показатели из МСФО, РСБУ и сканов, чтобы быстрее переходить от документа к решению.
          </Text>
        </Card>
        <Card radius="xl">
          <Text size="xs" fw={700} c="dimmed" tt="uppercase">Скоринг</Text>
          <Text fw={700} size="lg" mt={6}>Прозрачная финансовая оценка</Text>
          <Text size="sm" c="dimmed" mt="sm">
            Коэффициенты, факторы риска и пояснения собираются в единый отчёт без «чёрного ящика».
          </Text>
        </Card>
        <Card radius="xl">
          <Text size="xs" fw={700} c="dimmed" tt="uppercase">О сервисе</Text>
          <Text fw={700} size="lg" mt={6}>Живой демо-модуль экосистемы</Text>
          <Text size="sm" c="dimmed" mt="sm">
            {PRODUCT_DESCRIPTION}
          </Text>
        </Card>
      </SimpleGrid>
    </Stack>
  );
}
