from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Metric(BaseModel):
    """
    Представление отдельного финансового показателя,
    возвращаемого из API.
    """

    name: str = Field(..., description="Человекочитаемое имя показателя")
    value: float = Field(..., description="Числовое значение показателя")
    unit: str = Field(..., description="Единицы измерения (например, RUB, млн RUB, %) ")
    year: Optional[int] = Field(
        None,
        description="Год, к которому относится показатель (если удалось определить)",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Оценка уверенности извлечения (0–1)",
    )
    source_fragment: str = Field(
        ...,
        description="Фрагмент текста отчёта, из которого был извлечён показатель",
    )


class Ratio(BaseModel):
    """
    Представление рассчитанного финансового коэффициента.
    """

    name: str = Field(..., description="Название коэффициента")
    value: Optional[float] = Field(
        None,
        description="Числовое значение коэффициента (None, если рассчитать не удалось)",
    )
    unit: str = Field(
        ...,
        description="Единицы измерения коэффициента (например, %, x)",
    )
    year: Optional[int] = Field(
        None,
        description="Год, к которому относится коэффициент (если удалось определить)",
    )
    formula: str = Field(..., description="Формула коэффициента в текстовом виде")
    category: Optional[str] = Field(
        None,
        description="Категория коэффициента (ликвидность, рентабельность и т.п.)",
    )


class AnalyzeResponse(BaseModel):
    """
    Основная схема ответа эндпоинта /analyze.
    """

    raw_text: str = Field(
        ...,
        description="Сырой текст, извлечённый из PDF (для отладки и прозрачности)",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Предупреждения, связанные с качеством данных и обработкой",
    )
    metrics: list[Metric] = Field(
        default_factory=list,
        description="Извлечённые ключевые финансовые показатели",
    )
    ratios: list[Ratio] = Field(
        default_factory=list,
        description="Рассчитанные финансовые коэффициенты",
    )
    score: Optional[float] = Field(
        None,
        description="Интегральный скоринг компании по 100-балльной шкале (если рассчитан)",
    )

    # Заглушки под будущие модули NLP, рекомендаций и новостей
    nlp_summary: Optional[str] = Field(
        None,
        description="Краткое текстовое резюме пояснительной записки (будет заполняться на неделе 3)",
    )
    risks: list[str] = Field(
        default_factory=list,
        description="Список выявленных рисков (пока пустой, будет реализовано позже)",
    )
    opportunities: list[str] = Field(
        default_factory=list,
        description="Список выявленных перспектив/возможностей (пока пустой)",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Список рекомендаций (пока заглушка, будет реализовано позже)",
    )
    news: list[str] = Field(
        default_factory=list,
        description="Краткий список новостей и их тональности (опциональный модуль)",
    )

