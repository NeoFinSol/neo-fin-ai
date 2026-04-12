export type AnalysisStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'uploading'
  | 'cancelling'
  | 'cancelled';

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
  short_term_borrowings: number | null;
  long_term_borrowings: number | null;
  short_term_lease_liabilities: number | null;
  long_term_lease_liabilities: number | null;
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
  financial_leverage_total: number | null;
  financial_leverage_debt_only: number | null;
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

export interface ScoringMethodology {
  benchmark_profile: 'generic' | 'retail_demo';
  period_basis: 'reported' | 'annualized_q1' | 'annualized_h1';
  detection_mode: 'auto';
  reasons: string[];
  guardrails: string[];
  leverage_basis: 'total_liabilities' | 'debt_only';
  ifrs16_adjusted: boolean;
  adjustments: string[];
  peer_context: string[];
}

export interface ScoreData {
  score: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  confidence_score: number;
  factors: ScoreFactor[];
  normalized_scores: Partial<Record<keyof FinancialRatios, number | null>>;
  methodology?: ScoringMethodology;
}

export interface NLPResult {
  risks: string[];
  key_factors: string[];
  recommendations: string[];
}

export type AIRuntimeStatus = 'succeeded' | 'empty' | 'failed' | 'skipped';

export type AIRuntimeReasonCode =
  | 'no_nlp_content'
  | 'provider_unavailable'
  | 'provider_error'
  | 'invalid_response'
  | 'insufficient_text'
  | null;

export interface AIRuntimeInfo {
  requested_provider: AIProvider;
  effective_provider: Exclude<AIProvider, 'auto'> | null;
  status: AIRuntimeStatus;
  reason_code: AIRuntimeReasonCode;
}

// ---------------------------------------------------------------------------
// Confidence & Explainability types (neofin-competition-release)
// Requirement: 1.4
// ---------------------------------------------------------------------------

export type ExtractionSource =
  | 'table'
  | 'text'
  | 'ocr'
  | 'derived'
  | 'issuer_fallback'
  | 'table_exact'
  | 'table_partial'
  | 'text_regex'
  ;

export type EvidenceVersion = 'v1' | 'v2';
export type ExtractionMatchSemantics =
  | 'exact'
  | 'code_match'
  | 'section_match'
  | 'keyword_match'
  | 'not_applicable';
export type ExtractionInferenceMode =
  | 'direct'
  | 'derived'
  | 'approximation'
  | 'policy_override';
export type ExtractionPostprocessState = 'none' | 'guardrail_adjusted';

export interface ExtractionMetadataItem {
  evidence_version?: EvidenceVersion;
  confidence: number; // expected range [0.0, 1.0]
  source: ExtractionSource;
  match_semantics?: ExtractionMatchSemantics;
  inference_mode?: ExtractionInferenceMode;
  postprocess_state?: ExtractionPostprocessState;
  reason_code?: string | null;
  signal_flags?: string[];
  candidate_quality?: number | null;
  authoritative_override?: boolean;
}

// ---------------------------------------------------------------------------
// Decision Transparency types (Wave 7)
// ---------------------------------------------------------------------------

export type DecisionStepKind =
  | 'ranking'
  | 'confidence_filter'
  | 'guardrail'
  | 'llm_merge'
  | 'issuer_override';
export type DecisionAction =
  | 'selected'
  | 'dropped'
  | 'replaced'
  | 'invalidated'
  | 'merged'
  | 'overridden';
export type MetricFinalState =
  | 'selected'
  | 'absent'
  | 'filtered_out'
  | 'invalidated';
export type CandidateOutcomeKind =
  | 'winner'
  | 'loser'
  | 'filtered_out'
  | 'invalidated';

export interface DecisionStep {
  step: DecisionStepKind;
  action: DecisionAction;
  reason_code?: string | null;
  detail?: string | null;
}

export interface MetricCandidateTrace {
  candidate_id: string;
  profile_key: [string, string, string];
  value: number | null;
  confidence: number;
  quality_delta: number;
  structural_bonus: number;
  conflict_penalty: number;
  guardrail_penalty: number;
  candidate_quality: number | null;
  signal_flags: string[];
  reason_code?: string | null;
}

export interface CandidateOutcomeTrace {
  candidate: MetricCandidateTrace;
  outcome: CandidateOutcomeKind;
  outcome_step: DecisionStepKind;
  outcome_reason_code?: string | null;
}

export interface GuardrailEventWire {
  metric_key: string;
  stage: string;
  action: string;
  reason_code: string;
  before_value: number | null;
  after_value: number | null;
}

export interface MetricDecisionTrace {
  metric_key: string;
  final_state: MetricFinalState;
  outcomes: CandidateOutcomeTrace[];
  reason_path: DecisionStep[];
  guardrail_events?: GuardrailEventWire[] | null;
  human_summary: string;
}

export interface RejectionTrace {
  metric_key: string;
  winner_profile: [string, string, string];
  loser_profile: [string, string, string];
  reason_code: string;
  reason_detail?: string | null;
}

export interface IssuerOverrideTraceWire {
  metric_key: string;
  original_value: number | null;
  original_source: ExtractionSource;
  override_value: number | null;
  discrepancy_pct: number | null;
  reason_code: string;
}

export interface LLMMergeTrace {
  contributed: string[];
  rejected: RejectionTrace[];
}

export interface PipelineDecisionTrace {
  llm_merge: LLMMergeTrace | null;
  issuer_overrides: IssuerOverrideTraceWire[];
  confidence_threshold: number;
  policy_name: string;
  human_summary: string;
}

export interface DecisionTrace {
  per_metric: Record<string, MetricDecisionTrace>;
  pipeline: PipelineDecisionTrace;
  generated_at: string;
  is_complete: boolean;
  missing_components: string[];
  trace_version: string;
}

export interface AnalysisData {
  scanned: boolean;
  text: string;
  tables: any[];
  metrics: FinancialMetrics;
  ratios: FinancialRatios;
  score: ScoreData;
  nlp?: NLPResult;
  ai_runtime?: AIRuntimeInfo;
  extraction_metadata?: Record<string, ExtractionMetadataItem>;
  decision_trace?: DecisionTrace | null;
}

export interface AnalysisResponse {
  status: AnalysisStatus;
  data?: AnalysisData;
  error?: string;
}

export interface UploadResponse {
  task_id: string;
}

export type AIProvider = 'auto' | 'gigachat' | 'huggingface' | 'qwen' | 'ollama';

export interface AIProvidersResponse {
  default_provider: Exclude<AIProvider, 'auto'> | null;
  available_providers: AIProvider[];
}


// ---------------------------------------------------------------------------
// Analysis History API interfaces (analysis-history-visualization)
// Requirement: 6.4
// ---------------------------------------------------------------------------

export interface AnalysisSummary {
  task_id: string;
  status: string;
  created_at: string; // ISO 8601
  score: number | null;
  risk_level: string | null;
  filename: string | null;
}

export interface AnalysisListResponse {
  items: AnalysisSummary[];
  total: number;
  page: number;
  page_size: number;
}

// ---------------------------------------------------------------------------
// Multi-Period Analysis types (neofin-competition-release)
// Requirement: 2.6
// ---------------------------------------------------------------------------

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

export interface PeriodResult {
  period_label: string;
  ratios: Partial<Record<string, number | null>>;
  score: number | null;
  risk_level: RiskLevel | null;
  score_methodology?: ScoringMethodology | null;
  extraction_metadata: Record<string, ExtractionMetadataItem>;
  error?: string;
}

export interface MultiAnalysisProgress {
  completed: number;
  total: number;
}

export interface MultiAnalysisAcceptedResponse {
  session_id: string;
  status: 'processing';
}

export interface MultiAnalysisProcessingResponse {
  session_id: string;
  status: 'processing' | 'cancelling';
  progress: MultiAnalysisProgress;
}

export interface MultiAnalysisCompletedResponse {
  session_id: string;
  status: 'completed';
  periods: PeriodResult[];
}

export interface MultiAnalysisCancelledResponse {
  session_id: string;
  status: 'cancelled';
  progress: MultiAnalysisProgress;
}

export type MultiAnalysisResponse =
  | MultiAnalysisProcessingResponse
  | MultiAnalysisCompletedResponse
  | MultiAnalysisCancelledResponse;
