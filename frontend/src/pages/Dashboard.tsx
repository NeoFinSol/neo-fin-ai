import {
  Box, Card, Group, Text, Title, Stack, Progress, Alert, ThemeIcon, Timeline,
} from '@mantine/core';
import { Dropzone, FileRejection } from '@mantine/dropzone';
import {
  IconUpload, IconFileAnalytics, IconAlertCircle, IconX, IconLoader,
  IconBrain, IconChartBar, IconFileText, IconPhoto,
} from '@tabler/icons-react';
import { useCallback } from 'react';
import { DetailedReport } from './DetailedReport';
import { usePdfAnalysis } from '../hooks/usePdfAnalysis';

export function Dashboard() {
  const {
    mutate: analyze,
    isPending,
    statusText,
    isError,
    error,
    data,
    reset,
    progressStep, // Берем надежный шаг из хука
  } = usePdfAnalysis();

  const handleUpload = useCallback((files: File[]) => {
    if (files.length > 0) {
      analyze(files[0]);
    }
  }, [analyze]);

  // Обработка ошибок валидации Dropzone (размер, формат)
  const handleReject = useCallback((rejections: FileRejection[]) => {
    const message = rejections[0]?.errors[0]?.message || 'Файл отклонен';
    // Можно показать уведомление, но для MVP просто alert или игнор
    console.warn('File rejected:', message);
  }, []);

  if (data) {
    return <DetailedReport score={data.score} ratios={data.ratios} metrics={data.metrics} />;
  }

  return (
    <Stack gap="xl">
      <Box>
        <Title order={2} size="h3" mb={4}>
          ИИ-ассистент финансового директора
        </Title>
        <Text c="dimmed" size="sm">
          Автоматический анализ финансовой отчетности (МСФО/РСБУ)
        </Text>
      </Box>

      {isError && (
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

      <Card shadow="sm" padding="xl" radius="md" withBorder={!isPending}>
        {isPending ? (
          <Stack align="center" gap="lg" py="xl">
            <ThemeIcon size={60} radius="xl" color="blue" variant="light">
              {progressStep === 0 ? <IconUpload size={30} stroke={1.5} /> : <IconBrain size={30} stroke={1.5} />}
            </ThemeIcon>
            
            <Box w="100%">
              <Group justify="space-between" mb={5}>
                <Text size="sm" fw={500}>{statusText}</Text>
                {/* Спиннер показываем только пока грузимся, не на финальном экране */}
                {progressStep < 4 && <IconLoader size={16} className="animate-spin" />}
              </Group>
              <Progress value={100} animated size="sm" radius="xl" color="blue" />
            </Box>

            {/* Timeline полностью управляется progressStep из хука */}
            <Timeline active={progressStep} bulletSize={24} lineWidth={2} mt="md">
              <Timeline.Item bullet={<IconUpload size={12} />} title="Загрузка">
                <Text c="dimmed" size="xs">Отправка файла</Text>
              </Timeline.Item>
              <Timeline.Item bullet={<IconFileText size={12} />} title="Извлечение данных">
                <Text c="dimmed" size="xs">OCR, парсинг таблиц</Text>
              </Timeline.Item>
              <Timeline.Item bullet={<IconChartBar size={12} />} title="Расчет показателей">
                <Text c="dimmed" size="xs">Ликвидность, рентабельность</Text>
              </Timeline.Item>
              <Timeline.Item bullet={<IconBrain size={12} />} title="NLP Анализ">
                <Text c="dimmed" size="xs">Риски и рекомендации</Text>
              </Timeline.Item>
            </Timeline>

            <Text size="xs" c="dimmed" ta="center">
              Обработка может занять от 30 секунд до 5 минут
            </Text>
          </Stack>
        ) : (
          <Dropzone
            onDrop={handleUpload}
            onReject={handleReject}
            maxSize={50 * 1024 * 1024} // 50 MB
            accept={{ 'application/pdf': ['.pdf'] }}
            multiple={false} // Один файл за раз
            styles={{
              root: {
                borderStyle: 'dashed',
                borderWidth: 2,
                padding: '3rem',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                '&:hover': { backgroundColor: 'rgba(0, 40, 142, 0.02)' },
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
                <Text size="xl" inline>
                  Перетащите PDF-отчет сюда
                </Text>
                <Text size="sm" c="dimmed" mt={7}>
                  или нажмите для выбора файла
                </Text>
                <Text size="xs" c="dimmed" mt={12}>
                  Формат: PDF (до 50 МБ)
                </Text>
              </Box>
            </Group>
          </Dropzone>
        )}
      </Card>
    </Stack>
  );
}
