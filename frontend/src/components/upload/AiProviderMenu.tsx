import { SegmentedControl, Stack, Text } from '@mantine/core';

import type { AIProvider } from '../../api/interfaces';

const PROVIDER_LABELS: Record<AIProvider, string> = {
    auto: 'Авто',
    gigachat: 'GigaChat',
    huggingface: 'Hugging Face',
    qwen: 'Qwen',
    ollama: 'Ollama',
};

export function getAiProviderLabel(provider: AIProvider): string {
    return PROVIDER_LABELS[provider] ?? provider;
}

interface AiProviderMenuProps {
    value: AIProvider;
    options: AIProvider[];
    onChange: (provider: AIProvider) => void;
    disabled?: boolean;
}

export function AiProviderMenu({
    value,
    options,
    onChange,
    disabled = false,
}: AiProviderMenuProps) {
    return (
        <Stack gap={4} align="flex-end">
            <Text size="xs" c="dimmed">{`Провайдер: ${getAiProviderLabel(value)}`}</Text>
            <SegmentedControl
                size="xs"
                value={value}
                onChange={(nextValue) => onChange(nextValue as AIProvider)}
                disabled={disabled}
                data={options.map((option) => ({
                    label: getAiProviderLabel(option),
                    value: option,
                }))}
            />
        </Stack>
    );
}
