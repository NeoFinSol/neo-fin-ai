from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class FinanceMetric(BaseModel):
    name: str = Field(description="Человекочитаемое имя показателя")
    value: float = Field(description="Числовое значение показателя")
    unit: str = Field(description="Единицы измерения (например, RUB, млн RUB, %)")
    year: int | None = Field(description="Год, к которому относится показатель (если удалось определить)")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Оценка уверенности извлечения (0–1)")
    source_fragment: str = Field(description="Фрагмент текста отчёта, из которого был извлечён показатель")


class FinanceRatio(BaseModel):
    name: str = Field(description="Название коэффициента")
    value: float | None = Field(description="Числовое значение коэффициента (None, если рассчитать не удалось)")
    unit: str = Field(description="Единицы измерения коэффициента (например, %, x)")
    year: int | None = Field(description="Год, к которому относится коэффициент (если удалось определить)")
    formula: str = Field(description="Формула коэффициента в текстовом виде")
    category: str | None = Field(description="Категория коэффициента (ликвидность, рентабельность и т.п.)")


class AnalyzeResponse(BaseModel):
    raw_text: str = Field(description="Сырой текст, извлечённый из PDF (для отладки и прозрачности)")
    warnings: list[str] = Field(description="Предупреждения, связанные с качеством данных и обработкой")
    metrics: list[FinanceMetric] = Field(description="Извлечённые ключевые финансовые показатели")
    ratios: list[FinanceRatio] = Field(description="Рассчитанные финансовые коэффициенты")
    score: float | None = Field(description="Интегральный скоринг компании по 100-балльной шкале (если рассчитан)")

    # Заглушки под будущие модули NLP, рекомендаций и новостей
    nlp_summary: str | None = Field(description="Краткое текстовое резюме пояснительной записки (будет заполняться на неделе 3)")
    risks: list[str] = Field(description="Список выявленных рисков (пока пустой, будет реализовано позже)")
    opportunities: list[str] = Field(description="Список выявленных перспектив/возможностей (пока пустой)")
    recommendations: list[str] = Field(description="Список рекомендаций (пока заглушка, будет реализовано позже)")
    news: list[str] = Field(description="Краткий список новостей и их тональности (опциональный модуль)")


# ---------------------------------------------------------------------------
# Confidence & Explainability schemas (neofin-competition-release)
# Requirements: 1.2, 1.6
# ---------------------------------------------------------------------------


class ExtractionMetadataItem(BaseModel):
    confidence: float = Field(ge=0.0, le=1.0, description="Уверенность извлечения [0.0–1.0]")
    source: Literal["table_exact", "table_partial", "text_regex", "derived"] = Field(
        description="Метод извлечения показателя"
    )


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
# Multi-Period Analysis schemas (neofin-competition-release)
# Requirements: 2.3
# ---------------------------------------------------------------------------

RiskLevel = Literal["low", "medium", "high"]


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
    status: Literal["processing"]
    progress: MultiAnalysisProgress


class MultiAnalysisCompletedResponse(BaseModel):
    session_id: str
    status: Literal["completed"]
    periods: list[PeriodResult] = Field(min_length=1)


MultiAnalysisResponse = MultiAnalysisProcessingResponse | MultiAnalysisCompletedResponse
