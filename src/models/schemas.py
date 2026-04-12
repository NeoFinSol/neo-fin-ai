from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class FinanceMetric(BaseModel):
    name: str = Field(description="Человекочитаемое имя показателя")
    value: float = Field(description="Числовое значение показателя")
    unit: str = Field(description="Единицы измерения (например, RUB, млн RUB, %)")
    year: int | None = Field(
        description="Год, к которому относится показатель (если удалось определить)"
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0, description="Оценка уверенности извлечения (0–1)"
    )
    source_fragment: str = Field(
        description="Фрагмент текста отчёта, из которого был извлечён показатель"
    )


class FinanceRatio(BaseModel):
    name: str = Field(description="Название коэффициента")
    value: float | None = Field(
        description="Числовое значение коэффициента (None, если рассчитать не удалось)"
    )
    unit: str = Field(description="Единицы измерения коэффициента (например, %, x)")
    year: int | None = Field(
        description="Год, к которому относится коэффициент (если удалось определить)"
    )
    formula: str = Field(description="Формула коэффициента в текстовом виде")
    category: str | None = Field(
        description="Категория коэффициента (ликвидность, рентабельность и т.п.)"
    )


class AnalyzeResponse(BaseModel):
    raw_text: str = Field(
        description="Сырой текст, извлечённый из PDF (для отладки и прозрачности)"
    )
    warnings: list[str] = Field(
        description="Предупреждения, связанные с качеством данных и обработкой"
    )
    metrics: list[FinanceMetric] = Field(
        description="Извлечённые ключевые финансовые показатели"
    )
    ratios: list[FinanceRatio] = Field(
        description="Рассчитанные финансовые коэффициенты"
    )
    score: float | None = Field(
        description="Интегральный скоринг компании по 100-балльной шкале (если рассчитан)"
    )

    # Заглушки под будущие модули NLP, рекомендаций и новостей
    nlp_summary: str | None = Field(
        description="Краткое текстовое резюме пояснительной записки (будет заполняться на неделе 3)"
    )
    risks: list[str] = Field(
        description="Список выявленных рисков (пока пустой, будет реализовано позже)"
    )
    opportunities: list[str] = Field(
        description="Список выявленных перспектив/возможностей (пока пустой)"
    )
    recommendations: list[str] = Field(
        description="Список рекомендаций (пока заглушка, будет реализовано позже)"
    )
    news: list[str] = Field(
        description="Краткий список новостей и их тональности (опциональный модуль)"
    )


# ---------------------------------------------------------------------------
# Confidence & Explainability schemas (neofin-competition-release)
# Requirements: 1.2, 1.6
# ---------------------------------------------------------------------------


class ExtractionMetadataItem(BaseModel):
    evidence_version: Literal["v1", "v2"] = Field(
        default="v1",
        description="Версия explainability payload",
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Уверенность извлечения [0.0–1.0]"
    )
    source: Literal[
        "table",
        "text",
        "ocr",
        "derived",
        "issuer_fallback",
        "table_exact",
        "table_partial",
        "text_regex",
    ] = Field(description="Метод извлечения показателя")
    match_semantics: Literal[
        "exact",
        "code_match",
        "section_match",
        "keyword_match",
        "not_applicable",
    ] = Field(default="not_applicable", description="Семантика совпадения")
    inference_mode: Literal[
        "direct",
        "derived",
        "approximation",
        "policy_override",
    ] = Field(default="direct", description="Режим вывода значения")
    postprocess_state: Literal["none", "guardrail_adjusted"] = Field(
        default="none",
        description="Состояние постобработки",
    )
    reason_code: str | None = Field(
        default=None,
        description="Машинно-читаемая причина особого explainability-состояния",
    )
    signal_flags: list[str] = Field(
        default_factory=list,
        description="Список флагов сигналов и compatibility-маркеров",
    )
    candidate_quality: int | None = Field(
        default=None,
        description="Внутренний quality score кандидата",
    )
    authoritative_override: bool = Field(
        default=False,
        description="Признак policy override вместо обычного evidence score",
    )


class ScoreFactor(BaseModel):
    name: str = Field(description="Название фактора")
    description: str = Field(description="Описание влияния фактора")
    impact: Literal["positive", "negative", "neutral"] = Field(
        description="Тип влияния"
    )


class ScoreMethodologySchema(BaseModel):
    benchmark_profile: Literal["generic", "retail_demo"] = Field(
        description="Профиль бенчмарка для нормализации"
    )
    period_basis: Literal["reported", "annualized_q1", "annualized_h1"] = Field(
        description="База периода для скоринга"
    )
    detection_mode: Literal["auto"] = Field(description="Режим определения методики")
    reasons: list[str] = Field(description="Причины выбора профиля и базы периода")
    guardrails: list[str] = Field(description="Сработавшие data-quality guardrails")
    leverage_basis: Literal["total_liabilities", "debt_only"] = Field(
        description="Активная база финансового рычага"
    )
    ifrs16_adjusted: bool = Field(
        description="Применена ли IFRS 16-aware корректировка"
    )
    adjustments: list[str] = Field(
        description="Список применённых корректировок методики"
    )
    peer_context: list[str] = Field(description="Контекст отраслевых ориентиров")


class ScoreSchema(BaseModel):
    score: float = Field(ge=0.0, le=100.0, description="Итоговый балл")
    risk_level: str = Field(description="Уровень риска (low, medium, high, critical)")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Достоверность данных")
    factors: list[ScoreFactor] = Field(description="Список влияющих факторов")
    normalized_scores: dict[str, float | None] = Field(
        description="Нормализованные баллы по каждому коэффициенту"
    )
    methodology: ScoreMethodologySchema = Field(
        description="Методика расчёта интегрального скоринга"
    )


class AIRuntimeSchema(BaseModel):
    requested_provider: Literal["auto", "gigachat", "huggingface", "qwen", "ollama"] = (
        Field(description="Провайдер, запрошенный UI или автоматическим режимом")
    )
    effective_provider: Literal["gigachat", "huggingface", "qwen", "ollama"] | None = (
        Field(description="Провайдер, который реально использовался в AI-контуре")
    )
    status: Literal["succeeded", "empty", "failed", "skipped"] = Field(
        description="Результат выполнения AI-контура"
    )
    reason_code: (
        Literal[
            "no_nlp_content",
            "provider_unavailable",
            "provider_error",
            "invalid_response",
            "insufficient_text",
        ]
        | None
    ) = Field(description="Машинно-читаемая причина статуса")


# ---------------------------------------------------------------------------
# Analysis History API schemas (analysis-history-visualization)
# Requirements: 6.1, 6.2, 6.3
# ---------------------------------------------------------------------------


class AnalysisSummaryResponse(BaseModel):
    task_id: str
    status: str
    created_at: datetime
    score: float | None = None
    risk_level: str | None = None
    filename: str | None = None


class AnalysisListResponse(BaseModel):
    items: list[AnalysisSummaryResponse]
    total: int
    page: int
    page_size: int


class AnalysisDetailResponse(BaseModel):
    task_id: str
    status: str
    created_at: datetime
    data: dict | None = None
    extraction_metadata: dict[str, ExtractionMetadataItem] | None = None


# ---------------------------------------------------------------------------
# Decision Transparency schemas (Wave 7)
# ---------------------------------------------------------------------------


class DecisionStepSchema(BaseModel):
    step: str
    action: str
    reason_code: str | None = None
    detail: str | None = None


class MetricCandidateTraceSchema(BaseModel):
    candidate_id: str
    profile_key: tuple[str, str, str]
    value: float | None
    confidence: float
    quality_delta: float = 0.0
    structural_bonus: float = 0.0
    conflict_penalty: float = 0.0
    guardrail_penalty: float = 0.0
    candidate_quality: int | None = None
    signal_flags: list[str] = Field(default_factory=list)
    reason_code: str | None = None


class CandidateOutcomeTraceSchema(BaseModel):
    candidate: MetricCandidateTraceSchema
    outcome: str
    outcome_step: str
    outcome_reason_code: str | None = None


class MetricDecisionTraceSchema(BaseModel):
    metric_key: str
    final_state: str
    outcomes: list[CandidateOutcomeTraceSchema] = Field(default_factory=list)
    reason_path: list[DecisionStepSchema] = Field(default_factory=list)
    guardrail_events: list[dict] | None = None
    human_summary: str = ""


class RejectionTraceSchema(BaseModel):
    metric_key: str
    winner_profile: tuple[str, str, str]
    loser_profile: tuple[str, str, str]
    reason_code: str
    reason_detail: str | None = None


class IssuerOverrideTraceSchema(BaseModel):
    metric_key: str
    original_value: float | None
    original_source: str
    override_value: float | None
    discrepancy_pct: float | None
    reason_code: str


class LLMMergeTraceSchema(BaseModel):
    contributed: list[str] = Field(default_factory=list)
    rejected: list[RejectionTraceSchema] = Field(default_factory=list)


class PipelineDecisionTraceSchema(BaseModel):
    llm_merge: LLMMergeTraceSchema | None = None
    issuer_overrides: list[IssuerOverrideTraceSchema] = Field(default_factory=list)
    confidence_threshold: float
    policy_name: str
    human_summary: str = ""


class DecisionTraceSchema(BaseModel):
    per_metric: dict[str, MetricDecisionTraceSchema] = Field(default_factory=dict)
    pipeline: PipelineDecisionTraceSchema
    generated_at: str
    is_complete: bool = True
    missing_components: list[str] = Field(default_factory=list)
    trace_version: str = "v1"


# ---------------------------------------------------------------------------
# Multi-Period Analysis schemas (neofin-competition-release)
# Requirements: 2.3
# ---------------------------------------------------------------------------

RiskLevel = Literal["low", "medium", "high", "critical"]


class PeriodInput(BaseModel):
    period_label: str = Field(min_length=1, max_length=20)
    file_path: str = Field(description="Путь к временному PDF-файлу для этого периода")

    @field_validator("period_label", mode="before")
    @classmethod
    def strip_period_label(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("period_label must not be blank")
        return stripped


class PeriodResult(BaseModel):
    period_label: str
    ratios: dict[str, float | None]
    score: float | None
    risk_level: RiskLevel | None
    score_methodology: ScoreMethodologySchema | None = None
    extraction_metadata: dict[str, ExtractionMetadataItem]


class MultiAnalysisRequest(BaseModel):
    periods: list[PeriodInput] = Field(min_length=1, max_length=5)


class MultiAnalysisProgress(BaseModel):
    completed: int = Field(ge=0)
    total: int = Field(ge=0)


class MultiAnalysisAcceptedResponse(BaseModel):
    session_id: str
    status: Literal["processing"]


class MultiAnalysisProcessingResponse(BaseModel):
    session_id: str
    status: Literal["processing", "cancelling"]
    progress: MultiAnalysisProgress


class MultiAnalysisCompletedResponse(BaseModel):
    session_id: str
    status: Literal["completed"]
    periods: list[PeriodResult] = Field(min_length=1)


class MultiAnalysisCancelledResponse(BaseModel):
    session_id: str
    status: Literal["cancelled"]
    progress: MultiAnalysisProgress


MultiAnalysisResponse = (
    MultiAnalysisProcessingResponse
    | MultiAnalysisCompletedResponse
    | MultiAnalysisCancelledResponse
)
