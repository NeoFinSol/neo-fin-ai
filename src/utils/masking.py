"""
Модуль маскировки данных для демо-режима.

Чистая функция без side effects, без импортов FastAPI/SQLAlchemy.
"""

import copy
import math

MASKED_NONE_VALUE = "—"


def _mask_number(value: float | int | None) -> str:
    """
    Заменяет значащие цифры числа на 'X', сохраняя знак и порядок величины.

    Примеры:
        1234567.89  -> "X,XXX,XXX"
        0.85        -> "X.XX"
        -42.1       -> "-XX.X"
        0           -> "X"
        1000        -> "X,XXX"
        None        -> "—"
    """
    if value is None:
        return MASKED_NONE_VALUE

    negative = value < 0
    abs_val = abs(float(value))

    # Целая часть
    int_part = int(math.floor(abs_val))
    frac_part = abs_val - int_part

    # Определяем количество знаков дробной части из строкового представления
    str_repr = f"{abs_val}"
    if "." in str_repr:
        # Убираем trailing zeros, но сохраняем значащие цифры
        frac_digits_str = str_repr.split(".")[1].rstrip("0")
        frac_len = len(frac_digits_str)
    else:
        frac_len = 0

    # Маскируем целую часть с разделителями тысяч
    int_str = str(int_part)
    # Разбиваем на группы по 3 с конца
    groups = []
    while int_str:
        groups.append("X" * len(int_str[-3:]))
        int_str = int_str[:-3]
    masked_int = ",".join(reversed(groups)) if groups else "X"

    # Маскируем дробную часть
    if frac_len > 0:
        masked = masked_int + "." + "X" * frac_len
    else:
        masked = masked_int

    return ("-" + masked) if negative else masked


def _mask_dict_values(d: dict) -> dict:
    """Заменяет все числовые значения в словаре на строки-маски."""
    result = {}
    for key, value in d.items():
        if isinstance(value, bool):
            # bool — подкласс int, оставляем как есть
            result[key] = value
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            result[key] = _mask_number(value)
        else:
            result[key] = value
    return result


def mask_analysis_data(data: dict, demo_mode: bool) -> dict:
    """
    Чистая функция маскировки данных анализа для демо-режима.

    При demo_mode=True:
    - Заменяет числовые значения в data["data"]["metrics"] и data["data"]["ratios"]
      на строки-маски (сохраняет знак и порядок величины, цифры -> 'X').
    - Заменяет data["data"]["text"] на "[DEMO: текст скрыт]".
    - Сохраняет без изменений: score, risk_level, factors, normalized_scores, nlp.

    При demo_mode=False:
    - Возвращает данные без изменений (identity).

    Не мутирует входной словарь — возвращает новый (deep copy).
    """
    if not demo_mode:
        return data

    result = copy.deepcopy(data)

    inner = result.get("data")
    if not isinstance(inner, dict):
        return result

    # Маскируем metrics
    if isinstance(inner.get("metrics"), dict):
        inner["metrics"] = _mask_dict_values(inner["metrics"])

    # Маскируем ratios
    if isinstance(inner.get("ratios"), dict):
        inner["ratios"] = _mask_dict_values(inner["ratios"])

    # Маскируем text
    if "text" in inner:
        inner["text"] = "[DEMO: текст скрыт]"

    return result
