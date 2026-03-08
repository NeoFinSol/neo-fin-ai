from __future__ import annotations

from typing import Iterable, Optional

from .ratios import Ratio


def _find_ratio(ratios: Iterable[Ratio], startswith: str) -> Optional[Ratio]:
    for r in ratios:
        if r.name.startswith(startswith):
            return r
    return None


def _score_positive_ratio(value: Optional[float], target: float) -> Optional[float]:
    """
    Нормирует показатель, где «больше — лучше», к диапазону 0–1.
    При value >= target возвращает 1, при 0 — 0, между ними — линейная интерполяция.
    """
    if value is None:
        return None
    if value <= 0:
        return 0.0
    if value >= target:
        return 1.0
    return value / target


def _score_inverse_ratio(value: Optional[float], best: float, worst: float) -> Optional[float]:
    """
    Нормирует показатель, где «меньше — лучше» (например, Debt/Equity).
    - best: значение, при котором скор = 1
    - worst: значение, при котором скор = 0
    Между ними — линейная интерполяция, за пределами — отсечение.
    """
    if value is None:
        return None
    if value <= best:
        return 1.0
    if value >= worst:
        return 0.0
    # best < value < worst
    return 1.0 - (value - best) / (worst - best)


def calculate_score(ratios: list[Ratio]) -> Optional[float]:
    """
    Простейший интегральный скоринг (0–100) на основе ключевых коэффициентов.

    Важно: это технический черновик до появления детализированной методологии
    от аналитиков. Задача — иметь рабочий end-to-end пайплайн.
    """
    if not ratios:
        return None

    components: list[float] = []

    # Ликвидность: целевой текущий коэффициент ~ 2.0
    current_liquidity = _find_ratio(ratios, "Коэффициент текущей ликвидности")
    if current_liquidity is not None:
        s = _score_positive_ratio(current_liquidity.value, target=2.0)
        if s is not None:
            components.append(s)

    # Финансовая устойчивость: доля собственного капитала в активах (целевой >= 0.4)
    equity_ratio = _find_ratio(ratios, "Доля собственного капитала в активах")
    if equity_ratio is not None:
        s = _score_positive_ratio(equity_ratio.value, target=0.4)
        if s is not None:
            components.append(s)

    # Финансовый рычаг: Debt/Equity, оптимум ~ 1, критично >= 3
    leverage = _find_ratio(ratios, "Коэффициент финансового рычага")
    if leverage is not None:
        s = _score_inverse_ratio(leverage.value, best=1.0, worst=3.0)
        if s is not None:
            components.append(s)

    # Рентабельность: чистая маржа, ROA, ROE
    net_margin = _find_ratio(ratios, "Чистая рентабельность продаж")
    if net_margin is not None:
        s = _score_positive_ratio(net_margin.value, target=0.15)
        if s is not None:
            components.append(s)

    roa = _find_ratio(ratios, "Рентабельность активов (ROA)")
    if roa is not None:
        s = _score_positive_ratio(roa.value, target=0.08)
        if s is not None:
            components.append(s)

    roe = _find_ratio(ratios, "Рентабельность собственного капитала (ROE)")
    if roe is not None:
        s = _score_positive_ratio(roe.value, target=0.15)
        if s is not None:
            components.append(s)

    # Деловая активность: оборачиваемость активов (целевой >= 1)
    asset_turnover = _find_ratio(ratios, "Коэффициент оборачиваемости активов")
    if asset_turnover is not None:
        s = _score_positive_ratio(asset_turnover.value, target=1.0)
        if s is not None:
            components.append(s)

    if not components:
        return None

    # Среднее значение по всем доступным компонентам, в шкале 0–100
    raw_score = sum(components) / len(components)
    return round(raw_score * 100, 2)

