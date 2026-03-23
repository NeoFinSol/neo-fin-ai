export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface UploadResponse {
  task_id: string;
}

export interface FinancialMetrics {
  revenue?: number;
  net_profit?: number;
  total_assets?: number;
  equity?: number;
  liabilities?: number;
  current_assets?: number;
  short_term_liabilities?: number;
  accounts_receivable?: number;
}

export interface FinancialRatios {
  current_ratio?: number;
  equity_ratio?: number;
  roa?: number;
  roe?: number;
  debt_to_revenue?: number;
}

export interface ScoreData {
  score: number;
  risk_level: 'low' | 'medium' | 'high';
}

export interface AnalysisResult {
  scanned: boolean;
  text: string;
  tables: any[];
  metrics: FinancialMetrics;
  ratios: FinancialRatios;
  score: ScoreData;
}

export interface AnalysisResponse {
  status: AnalysisStatus;
  result?: AnalysisResult;
  error?: string;
}
