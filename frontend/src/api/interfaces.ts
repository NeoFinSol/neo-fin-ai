export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'uploading';

export interface FinancialMetrics {
  revenue: number | null;
  net_profit: number | null;
  total_assets: number | null;
  equity: number | null;
  liabilities: number | null;
  current_assets: number | null;
  short_term_liabilities: number | null;
  accounts_receivable: number | null;
  inventory: number | null;
  cash_and_equivalents: number | null;
  ebitda: number | null;
  ebit: number | null;
  interest_expense: number | null;
  cost_of_goods_sold: number | null;
  average_inventory: number | null;
}

// All 12 ratios across 4 groups (РСБУ/МСФО standard)
export interface FinancialRatios {
  // Liquidity
  current_ratio: number | null;
  quick_ratio: number | null;
  absolute_liquidity_ratio: number | null;
  // Profitability
  roa: number | null;
  roe: number | null;
  ros: number | null;
  ebitda_margin: number | null;
  // Financial stability
  equity_ratio: number | null;
  financial_leverage: number | null;
  interest_coverage: number | null;
  // Business activity
  asset_turnover: number | null;
  inventory_turnover: number | null;
  receivables_turnover: number | null;
}

export interface ScoreFactor {
  name: string;
  description: string;
  impact: 'positive' | 'negative' | 'neutral';
}

export interface ScoreData {
  score: number;
  risk_level: 'low' | 'medium' | 'high';
  factors: ScoreFactor[];
  normalized_scores: Partial<Record<keyof FinancialRatios, number | null>>;
}

export interface NLPResult {
  risks: string[];
  key_factors: string[];
  recommendations: string[];
}

export interface AnalysisData {
  scanned: boolean;
  text: string;
  tables: any[];
  metrics: FinancialMetrics;
  ratios: FinancialRatios;
  score: ScoreData;
  nlp?: NLPResult;
}

export interface AnalysisResponse {
  status: AnalysisStatus;
  data?: AnalysisData;
  error?: string;
}

export interface UploadResponse {
  task_id: string;
}
