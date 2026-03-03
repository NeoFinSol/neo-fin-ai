from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .extractor import Metric


@dataclass
class Ratio:
    name: str
    value: Optional[float]
    unit: str
    year: Optional[int]
    formula: str
    category: Optional[str] = None


def _get_metric_value(
    metrics: Iterable[Metric],
    metric_name: str,
    year: Optional[int] = None,
) -> Optional[float]:
    """
    Возвращает значение показателя по имени (и, опционально, году).
    Если показатель не найден, возвращает None.
    """
    for m in metrics:
        if m.name != metric_name:
            continue
        if year is not None and m.year is not None and m.year != year:
            continue
        return m.value
    return None


def _safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    return numerator / denominator


def calculate_ratios(metrics: list[Metric]) -> list[Ratio]:
    """
    Рассчитывает базовый набор финансовых коэффициентов на основе извлечённых показателей.

    Набор коэффициентов (минимум 12), ориентированный на стандартные группы:
    - Ликвидность
    - Финансовая устойчивость
    - Рентабельность
    - Деловая активность
    - Динамика выручки
    """
    # В текущей реализации год не извлекается надёжно, поэтому считаем коэффициенты
    # в разрезе "последнего доступного значения" (year=None).
    year = None

    revenue = _get_metric_value(metrics, "revenue", year)
    cogs = _get_metric_value(metrics, "cogs", year)
    operating_profit = _get_metric_value(metrics, "operating_profit", year)
    ebitda = _get_metric_value(metrics, "ebitda", year)
    net_income = _get_metric_value(metrics, "net_income", year)
    total_assets = _get_metric_value(metrics, "total_assets", year)
    total_liabilities = _get_metric_value(metrics, "total_liabilities", year)
    equity = _get_metric_value(metrics, "equity", year)
    current_assets = _get_metric_value(metrics, "current_assets", year)
    current_liabilities = _get_metric_value(metrics, "current_liabilities", year)
    inventories = _get_metric_value(metrics, "inventories", year)

    ratios: list[Ratio] = []

    # Ликвидность
    ratios.append(
        Ratio(
            name="Коэффициент текущей ликвидности",
            value=_safe_div(current_assets, current_liabilities),
            unit="x",
            year=year,
            formula="Оборотные активы / Краткосрочные обязательства",
            category="Ликвидность",
        ),
    )
    ratios.append(
        Ratio(
            name="Коэффициент быстрой ликвидности",
            value=_safe_div(
                None if current_assets is None or inventories is None else current_assets - inventories,
                current_liabilities,
            ),
            unit="x",
            year=year,
            formula="(Оборотные активы − Запасы) / Краткосрочные обязательства",
            category="Ликвидность",
        ),
    )

    # Финансовая устойчивость
    ratios.append(
        Ratio(
            name="Доля собственного капитала в активах",
            value=_safe_div(equity, total_assets),
            unit="%",
            year=year,
            formula="Собственный капитал / Активы",
            category="Финансовая устойчивость",
        ),
    )
    ratios.append(
        Ratio(
            name="Коэффициент финансового рычага (Debt/Equity)",
            value=_safe_div(total_liabilities, equity),
            unit="x",
            year=year,
            formula="Обязательства / Собственный капитал",
            category="Финансовая устойчивость",
        ),
    )

    # Рентабельность
    gross_profit = None
    if revenue is not None and cogs is not None:
        gross_profit = revenue - cogs

    ratios.append(
        Ratio(
            name="Валовая рентабельность продаж",
            value=_safe_div(gross_profit, revenue),
            unit="%",
            year=year,
            formula="(Выручка − Себестоимость) / Выручка",
            category="Рентабельность",
        ),
    )
    ratios.append(
        Ratio(
            name="Операционная рентабельность продаж",
            value=_safe_div(operating_profit, revenue),
            unit="%",
            year=year,
            formula="Операционная прибыль / Выручка",
            category="Рентабельность",
        ),
    )
    ratios.append(
        Ratio(
            name="Рентабельность продаж по EBITDA",
            value=_safe_div(ebitda, revenue),
            unit="%",
            year=year,
            formula="EBITDA / Выручка",
            category="Рентабельность",
        ),
    )
    ratios.append(
        Ratio(
            name="Чистая рентабельность продаж",
            value=_safe_div(net_income, revenue),
            unit="%",
            year=year,
            formula="Чистая прибыль / Выручка",
            category="Рентабельность",
        ),
    )
    ratios.append(
        Ratio(
            name="Рентабельность активов (ROA)",
            value=_safe_div(net_income, total_assets),
            unit="%",
            year=year,
            formula="Чистая прибыль / Активы",
            category="Рентабельность",
        ),
    )
    ratios.append(
        Ratio(
            name="Рентабельность собственного капитала (ROE)",
            value=_safe_div(net_income, equity),
            unit="%",
            year=year,
            formula="Чистая прибыль / Собственный капитал",
            category="Рентабельность",
        ),
    )

    # Деловая активность
    ratios.append(
        Ratio(
            name="Коэффициент оборачиваемости активов",
            value=_safe_div(revenue, total_assets),
            unit="x",
            year=year,
            formula="Выручка / Активы",
            category="Деловая активность",
        ),
    )

    # Динамика
    ratios.append(
        Ratio(
            name="Рост выручки год к году",
            value=None,  # будет доработано при появлении многолетних данных
            unit="%",
            year=year,
            formula="(Выручка_t − Выручка_{t-1}) / Выручка_{t-1}",
            category="Динамика",
        ),
    )

    return ratios

