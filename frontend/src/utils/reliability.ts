import { AnalysisData, ExtractionMetadataItem } from '../api/interfaces';
import { REPORT_CONFIDENCE_THRESHOLD } from '../constants/report';

export function survivesConfidenceFilter(
    item: ExtractionMetadataItem | undefined,
    threshold: number = REPORT_CONFIDENCE_THRESHOLD
): boolean {
    if (!item) {
        return false;
    }

    if (item.authoritative_override) {
        return true;
    }

    return item.confidence >= threshold;
}

export function countReliableMetrics(
    extractionMetadata: AnalysisData['extraction_metadata'],
    threshold: number = REPORT_CONFIDENCE_THRESHOLD
): number {
    if (!extractionMetadata) {
        return 0;
    }

    return Object.values(extractionMetadata).filter(
        (item) => survivesConfidenceFilter(item, threshold)
    ).length;
}
