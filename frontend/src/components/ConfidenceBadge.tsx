import React from 'react';
import { Tooltip, Text, Stack } from '@mantine/core';
import { ExtractionSource } from '../api/interfaces';

interface ConfidenceBadgeProps {
    metricKey: string;
    confidence: number;
    source: ExtractionSource;
}

interface SourceInfo {
    label: string;
    method: string;
}

const SOURCE_INFO: Record<ExtractionSource, SourceInfo> = {
    table_exact: { label: 'Table match (exact)', method: 'Exact keyword match in table' },
    table_partial: { label: 'Table match (partial)', method: 'Partial keyword match in table' },
    text_regex: { label: 'Text extraction (regex)', method: 'Regular expression in text' },
    derived: { label: 'Derived or fallback value', method: 'Calculated from other metrics' },
    issuer_fallback: { label: 'Issuer fallback', method: 'Repo-versioned issuer truth source override' },
};

interface LevelConfig {
    color: string;
    emoji: string;
    label: string;
}

const LEVEL_CONFIG: Record<'high' | 'medium' | 'low', LevelConfig> = {
    high: { color: '#2f9e44', emoji: '🟢', label: 'High' },
    medium: { color: '#e67700', emoji: '🟡', label: 'Medium' },
    low: { color: '#c92a2a', emoji: '🔴', label: 'Low' },
};

const BADGE_STYLE: React.CSSProperties = { cursor: 'default', display: 'inline-flex', alignItems: 'center', gap: 4 };

function getLevel(confidence: number): 'high' | 'medium' | 'low' {
    if (confidence > 0.8) return 'high';
    if (confidence >= 0.5) return 'medium';
    return 'low';
}

function safeConfidence(value: number): number {
    return Number.isFinite(value) ? value : 0;
}

const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({ metricKey: _metricKey, confidence, source }) => {
    const c = safeConfidence(confidence);
    const { color, emoji, label } = LEVEL_CONFIG[getLevel(c)];
    const { label: sourceLabel, method } = SOURCE_INFO[source];

    const tooltipLabel = (
        <Stack gap={2}>
            <Text size="xs">Источник: {sourceLabel}</Text>
            <Text size="xs">Метод: {method}</Text>
            <Text size="xs">Уверенность: {label} ({c.toFixed(2)})</Text>
        </Stack>
    );

    return (
        <Tooltip label={tooltipLabel} withArrow position="top">
            <span style={BADGE_STYLE}>
                <span style={{ fontSize: 12 }}>{emoji}</span>
                <Text size="xs" c={color} fw={500}>{c.toFixed(2)}</Text>
            </span>
        </Tooltip>
    );
};

export default ConfidenceBadge;
