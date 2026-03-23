import React, { useState, useEffect } from 'react';
import { Title, Text, SimpleGrid, Card, Group, Stack, Progress, Badge, Box, ThemeIcon, rem, Button } from '@mantine/core';
import { Dropzone, PDF_MIME_TYPE } from '@mantine/dropzone';
import { FileSearch, Upload, X, FileText, TrendingUp, ShieldCheck, Activity, AlertTriangle } from 'lucide-react';
import { usePdfAnalysis } from '../hooks/usePdfAnalysis';
import { useNavigate } from 'react-router-dom';

export const Dashboard = () => {
  const { uploadPdf, status, result, error, isProcessing, isIdle } = usePdfAnalysis();
  const navigate = useNavigate();

  useEffect(() => {
    if (status === 'completed' && result) {
      // Optional: auto-navigate or just show button
      // navigate('/reports', { state: { result } });
    }
  }, [status, result, navigate]);

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'low': return '#00714d';
      case 'medium': return '#f59e0b';
      case 'high': return '#ba1a1a';
      default: return '#6b7280';
    }
  };

  const getRiskLabel = (risk: string) => {
    switch (risk) {
      case 'low': return 'НИЗКИЙ РИСК';
      case 'medium': return 'СРЕДНИЙ РИСК';
      case 'high': return 'ВЫСОКИЙ РИСК';
      default: return 'НЕИЗВЕСТНО';
    }
  };

  const [fileName, setFileName] = useState<string | null>(null);
  const [fakeProgress, setFakeProgress] = useState(0);

  useEffect(() => {
    let interval: number;
    if (isProcessing) {
      setFakeProgress(0);
      interval = window.setInterval(() => {
        setFakeProgress((prev) => {
          if (status === 'uploading') {
            return prev < 30 ? prev + 2 : prev;
          }
          if (prev < 90) return prev + 1;
          return prev;
        });
      }, 200);
    } else {
      setFakeProgress(0);
    }
    return () => window.clearInterval(interval);
  }, [isProcessing, status]);

  const handleUpload = (file: File) => {
    setFileName(file.name);
    uploadPdf(file);
  };

  return (
    <Stack gap="xl">
      <header>
        <Title order={1} style={{ letterSpacing: '-0.02em' }}>Анализ финансовой отчетности с ИИ</Title>
        <Text c="dimmed" size="lg" mt="xs">
          Загрузите PDF и получите детальный скоринг компании за считанные секунды.
        </Text>
      </header>

      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="xl">
        <Card bg="#f3f4f5">
          <Title order={3} mb="md">Загрузка документа</Title>
          <Dropzone
            onDrop={(files) => handleUpload(files[0])}
            maxSize={50 * 1024 ** 2}
            accept={PDF_MIME_TYPE}
            loading={isProcessing}
            radius="md"
            styles={{
              root: {
                backgroundColor: '#ffffff',
                border: '2px dashed #dee2e6',
                '&:hover': {
                  backgroundColor: '#f8f9fa',
                },
              },
            }}
          >
            <Group justify="center" gap="xl" mih={220} style={{ pointerEvents: 'none' }}>
              <Dropzone.Accept>
                <Upload size={rem(52)} color="var(--mantine-color-blue-6)" />
              </Dropzone.Accept>
              <Dropzone.Reject>
                <X size={rem(52)} color="var(--mantine-color-red-6)" />
              </Dropzone.Reject>
              <Dropzone.Idle>
                <FileSearch size={rem(52)} color="#00288e" />
              </Dropzone.Idle>

              <div>
                <Text size="xl" inline fw={700}>
                  Перетащите PDF сюда или кликните для выбора
                </Text>
                <Text size="sm" c="dimmed" inline mt={7}>
                  Макс. размер 50 МБ, до 100 страниц
                </Text>
              </div>
            </Group>
          </Dropzone>

          {isProcessing && (
            <Stack mt="xl">
              <Group justify="space-between">
                <Text size="sm" fw={600}>Обработка данных...</Text>
                <Text size="xs" c="dimmed" style={{ fontFamily: 'JetBrains Mono' }}>
                  {fakeProgress}%
                </Text>
              </Group>
              <Progress value={fakeProgress} animated color="#00288e" size="sm" />
            </Stack>
          )}

          {error && (
            <Group mt="md" c="red">
              <AlertTriangle size={16} />
              <Text size="sm" fw={500}>{error}</Text>
            </Group>
          )}
        </Card>

        <Card>
          <Title order={3} mb="md">Статус обработки</Title>
          {isIdle ? (
            <Stack align="center" justify="center" mih={200} c="dimmed">
              <FileText size={48} strokeWidth={1} />
              <Text mt="md">Ожидание загрузки файла...</Text>
            </Stack>
          ) : (
            <Stack gap="md">
              <Group justify="space-between">
                <Text fw={600}>Файл:</Text>
                <Text size="sm" c="dimmed">{fileName || 'financial_report.pdf'}</Text>
              </Group>
              <Group justify="space-between">
                <Text fw={600}>Статус:</Text>
                <Badge 
                  variant="light" 
                  color={status === 'completed' ? 'green' : status === 'failed' ? 'red' : 'blue'}
                >
                  {status === 'completed' ? 'Готово' : status === 'failed' ? 'Ошибка' : 'В процессе'}
                </Badge>
              </Group>
              <Text size="sm" c="dimmed" mt="sm">
                ИИ анализирует балансовые показатели и рассчитывает коэффициенты ликвидности.
              </Text>
              {status === 'completed' && result && (
                <Button 
                  fullWidth 
                  mt="md" 
                  onClick={() => navigate('/reports', { state: { result, filename: fileName } })}
                  rightSection={<TrendingUp size={16} />}
                >
                  Открыть полный отчет
                </Button>
              )}
            </Stack>
          )}
        </Card>
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, sm: 2, xl: 4 }} spacing="xl">
        <MetricCard 
          title="Общий скоринг" 
          value={result?.score.score} 
          maxValue={100}
          icon={ShieldCheck}
          color="blue"
          loading={isProcessing}
          badge={result ? getRiskLabel(result.score.risk_level) : undefined}
          badgeColor={result ? getRiskColor(result.score.risk_level) : undefined}
        />
        <MetricCard 
          title="Ликвидность" 
          value={result?.ratios.current_ratio} 
          icon={Activity}
          color="teal"
          loading={isProcessing}
          suffix=""
        />
        <MetricCard 
          title="Рентабельность" 
          value={result?.ratios.roe ? result.ratios.roe * 100 : undefined} 
          icon={TrendingUp}
          color="indigo"
          loading={isProcessing}
          suffix="%"
        />
        <MetricCard 
          title="Долговая нагрузка" 
          value={result?.ratios.debt_to_revenue} 
          icon={AlertTriangle}
          color="orange"
          loading={isProcessing}
        />
      </SimpleGrid>
    </Stack>
  );
};

interface MetricCardProps {
  title: string;
  value?: number;
  maxValue?: number;
  icon: any;
  color: string;
  loading: boolean;
  suffix?: string;
  badge?: string;
  badgeColor?: string;
}

const MetricCard = ({ title, value, maxValue, icon: Icon, color, loading, suffix = '', badge, badgeColor }: MetricCardProps) => {
  return (
    <Card>
      <Stack gap="xs">
        <Group justify="space-between">
          <Text size="xs" c="dimmed" tt="uppercase" fw={700} style={{ letterSpacing: '0.05em' }}>
            {title}
          </Text>
          <ThemeIcon variant="light" color={color} size="sm">
            <Icon size={14} />
          </ThemeIcon>
        </Group>
        
        <Box mih={40}>
          {loading ? (
            <Progress value={100} animated size="xs" mt="md" color="#00288e" />
          ) : value !== undefined ? (
            <Group align="baseline" gap={4}>
              <Text size="xl" fw={800} style={{ fontFamily: 'JetBrains Mono' }}>
                {value.toFixed(2)}
              </Text>
              {maxValue && (
                <Text size="sm" c="dimmed" style={{ fontFamily: 'JetBrains Mono' }}>
                  /{maxValue}
                </Text>
              )}
              {suffix && (
                <Text size="sm" fw={700} c="dimmed">
                  {suffix}
                </Text>
              )}
            </Group>
          ) : (
            <Text c="dimmed" size="xl" fw={800} style={{ fontFamily: 'JetBrains Mono' }}>
              —
            </Text>
          )}
        </Box>

        {badge && (
          <Badge 
            variant="filled" 
            bg={badgeColor === '#00714d' ? '#6cf8bb' : badgeColor === '#f59e0b' ? '#fef3c7' : '#ffdad6'} 
            c={badgeColor} 
            size="sm" 
            mt="xs"
            fw={700}
          >
            {badge}
          </Badge>
        )}
      </Stack>
    </Card>
  );
};
