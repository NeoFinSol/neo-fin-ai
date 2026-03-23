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
}

export interface FinancialRatios {
  current_ratio: number | null;
  equity_ratio: number | null;
  roa: number | null;
  roe: number | null;
  debt_to_revenue: number | null;
}

export interface ScoreData {
  score: number;
  risk_level: 'low' | 'medium' | 'high';
  factors: {
    name: string;
    description: string;
    impact: 'positive' | 'negative' | 'neutral';
  }[];
  normalized_scores: {
    current_ratio: number | null;
    equity_ratio: number | null;
    roa: number | null;
    roe: number | null;
    debt_to_revenue: number | null;
  };
}

export interface NLPResult {
  // Backend schema: src/tasks.py -> nlp_result
  // Keys use snake_case to match Python backend
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
  nlp?: NLPResult;  // Optional - may be absent if AI not configured or analysis failed
}

export interface AnalysisResponse {
  status: AnalysisStatus;
  data?: AnalysisData;
  error?: string;
}

export interface UploadResponse {
  task_id: string;
}
