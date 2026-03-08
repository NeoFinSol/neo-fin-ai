from __future__ import annotations

from pydantic import BaseModel, Field


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
