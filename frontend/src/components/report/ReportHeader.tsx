import { Button, Group, Stack, Text, Title } from '@mantine/core';
import { Download, Printer } from 'lucide-react';

interface ReportHeaderProps {
    filename?: string;
    transactionId: string;
    onPrint: () => void;
}

export default function ReportHeader({
    filename,
    transactionId,
    onPrint,
}: ReportHeaderProps) {
    return (
        <Group justify="space-between" align="center">
            <Stack gap={4}>
                <Title order={1} style={{ letterSpacing: '-0.02em', fontWeight: 800 }}>
                    Отчет об анализе: {filename || 'Финансовый документ'}
                </Title>
                <Text c="dimmed" size="sm">ID Транзакции: {transactionId}</Text>
            </Stack>
            <Group gap="md">
                <Button variant="subtle" leftSection={<Printer size={18} />} onClick={onPrint} color="gray">
                    Печать
                </Button>
                <Button variant="filled" leftSection={<Download size={18} />} bg="#00288e">
                    Скачать PDF
                </Button>
            </Group>
        </Group>
    );
}
