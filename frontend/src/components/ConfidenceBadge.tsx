import React from 'react';
import { Tooltip, Text, Stack } from '@mantine/core';
import {
    ExtractionInferenceMode,
    ExtractionMatchSemantics,
    ExtractionSource,
} from '../api/interfaces';

interface ConfidenceBadgeProps {
    metricKey: string;
    confidence: number;
    source: ExtractionSource;
    matchSemantics?: ExtractionMatchSemantics;
    inferenceMode?: ExtractionInferenceMode;
    reasonCode?: string | null;
    authoritativeOverride?: boolean;
}

interface SourceInfo {
    label: string;
    method: string;
}

const SOURCE_INFO: Record<ExtractionSource, SourceInfo> = {
    table: { label: 'Table evidence', method: 'Structured table extraction' },
    text: { label: 'Text evidence', method: 'Narrative or line-based text extraction' },
    ocr: { label: 'OCR evidence', method: 'OCR-assisted structural extraction' },
    derived: { label: 'Derived value', method: 'Calculated from accepted metrics' },
    issuer_fallback: { label: 'Issuer fallback', method: 'Repo-versioned issuer truth source override' },
    table_exact: { label: 'Table match (exact)', method: 'Exact keyword match in table' },
    table_partial: { label: 'Table match (partial)', method: 'Partial keyword match in table' },
    text_regex: { label: 'Text extraction (regex)', method: 'Regular expression in text' },
};

const MATCH_LABELS: Partial<Record<ExtractionMatchSemantics, string>> = {
    exact: 'Exact',
    code_match: 'Code match',
    section_match: 'Section match',
    keyword_match: 'Keyword match',
    not_applicable: 'Not applicable',
};

const INFERENCE_LABELS: Partial<Record<ExtractionInferenceMode, string>> = {
    direct: 'Direct evidence',
    derived: 'Derived formula',
    approximation: 'Approximation',
    policy_override: 'Policy override',
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

const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({
    metricKey: _metricKey,
    confidence,
    source,
    matchSemantics,
    inferenceMode,
    reasonCode,
    authoritativeOverride = false,
}) => {
    const c = safeConfidence(confidence);
    const { color, emoji, label } = LEVEL_CONFIG[getLevel(c)];
    const { label: sourceLabel, method } = SOURCE_INFO[source];
    const matchLabel = matchSemantics ? MATCH_LABELS[matchSemantics] : null;
    const inferenceLabel = inferenceMode ? INFERENCE_LABELS[inferenceMode] : null;

    const tooltipLabel = (
        <Stack gap={2}>
            <Text size="xs">Источник: {sourceLabel}</Text>
            <Text size="xs">Метод: {method}</Text>
            {matchLabel ? <Text size="xs">Совпадение: {matchLabel}</Text> : null}
            {inferenceLabel ? <Text size="xs">Режим: {inferenceLabel}</Text> : null}
            {reasonCode ? <Text size="xs">Причина: {reasonCode}</Text> : null}
            {authoritativeOverride ? (
                <Text size="xs">Политика: авторитетный override</Text>
            ) : null}
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
