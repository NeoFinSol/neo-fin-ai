import { FinancialRatios } from '../api/interfaces';

export const THRESHOLDS: Partial<Record<keyof FinancialRatios, number>> = {
    current_ratio: 2.0,
    quick_ratio: 1.0,
    roa: 0.05,
    roe: 0.10,
    equity_ratio: 0.5,
};

const RATIO_LABELS: Partial<Record<keyof FinancialRatios, string>> = {
    current_ratio: 'Тек. ликвидность',
    quick_ratio: 'Быстрая ликв.',
    absolute_liquidity_ratio: 'Абс. ликвидность',
    roa: 'ROA',
    roe: 'ROE',
    ros: 'ROS',
    ebitda_margin: 'EBITDA margin',
    equity_ratio: 'Автономия',
    financial_leverage: 'Фин. рычаг',
    interest_coverage: 'Покрытие %',
    asset_turnover: 'Оборач. активов',
    inventory_turnover: 'Оборач. запасов',
    receivables_turnover: 'Оборач. деб. зад.',
};

export interface ChartDataPoint {
    label: string;
    value: number;
    color: string;
    key: string;
}

export function getBarColor(key: keyof FinancialRatios, value: number): string {
    const threshold = THRESHOLDS[key];
    if (threshold === undefined) return 'blue.6';
    return value >= threshold ? 'teal.6' : 'red.5';
}

export function buildChartData(ratios: FinancialRatios): ChartDataPoint[] {
    return (Object.keys(ratios) as Array<keyof FinancialRatios>)
        .filter((key) => {
            const v = ratios[key];
            return v !== null && v !== 0;
        })
        .map((key) => ({
            key,
            label: RATIO_LABELS[key] ?? key,
            value: ratios[key] as number,
            color: getBarColor(key, ratios[key] as number),
        }));
}
