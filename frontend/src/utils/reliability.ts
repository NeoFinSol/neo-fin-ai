import { AnalysisData } from '../api/interfaces';
import { REPORT_CONFIDENCE_THRESHOLD } from '../constants/report';

export function countReliableMetrics(
    extractionMetadata: AnalysisData['extraction_metadata'],
    threshold: number = REPORT_CONFIDENCE_THRESHOLD
): number {
    if (!extractionMetadata) {
        return 0;
    }

    return Object.values(extractionMetadata).filter(
        (item) => item.confidence >= threshold
    ).length;
}
