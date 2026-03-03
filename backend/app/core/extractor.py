from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class Metric:
    """
    Внутреннее представление извлечённого финансового показателя.
    """

    name: str
    value: float
    unit: str
    year: Optional[int]
    confidence_score: float
    source_fragment: str


_METRIC_DEFINITIONS = [
    # Выручка
    {
        "key": "revenue",
        "name": "Выручка",
        "patterns": [
            r"выручка(?: от продаж)?",
            r"revenue",
            r"sales",
        ],
        "unit": "RUB",
    },
    # Себестоимость
    {
        "key": "cogs",
        "name": "Себестоимость",
        "patterns": [
            r"себестоимост[ьи] продаж",
            r"себестоимость реализованной продукции",
            r"cost of sales",
            r"cost of goods sold",
        ],
        "unit": "RUB",
    },
    # Операционная прибыль
    {
        "key": "operating_profit",
        "name": "Операционная прибыль",
        "patterns": [
            r"операционн[аяой]* прибыль",
            r"прибыль от основной деятельности",
            r"operating profit",
            r"ebit(?!da)",
        ],
        "unit": "RUB",
    },
    # EBITDA
    {
        "key": "ebitda",
        "name": "EBITDA",
        "patterns": [
            r"ebitda",
        ],
        "unit": "RUB",
    },
    # Чистая прибыль
    {
        "key": "net_income",
        "name": "Чистая прибыль",
        "patterns": [
            r"чист[аяой]* прибыль",
            r"net profit",
            r"net income",
        ],
        "unit": "RUB",
    },
    # Активы всего
    {
        "key": "total_assets",
        "name": "Итого активы",
        "patterns": [
            r"итого активы",
            r"активы всего",
            r"total assets",
        ],
        "unit": "RUB",
    },
    # Обязательства всего
    {
        "key": "total_liabilities",
        "name": "Итого обязательства",
        "patterns": [
            r"итого обязательств[а]?",
            r"обязательства всего",
            r"total liabilities",
        ],
        "unit": "RUB",
    },
    # Собственный капитал
    {
        "key": "equity",
        "name": "Собственный капитал",
        "patterns": [
            r"собственн[ыйого]* капитал",
            r"equity",
            r"shareholders' equity",
        ],
        "unit": "RUB",
    },
    # Оборотные активы
    {
        "key": "current_assets",
        "name": "Оборотные активы",
        "patterns": [
            r"оборотные активы",
            r"current assets",
        ],
        "unit": "RUB",
    },
    # Краткосрочные обязательства
    {
        "key": "current_liabilities",
        "name": "Краткосрочные обязательства",
        "patterns": [
            r"краткосрочн[ыеых]* обязательства",
            r"текущие обязательства",
            r"current liabilities",
        ],
        "unit": "RUB",
    },
    # Запасы
    {
        "key": "inventories",
        "name": "Запасы",
        "patterns": [
            r"запасы",
            r"inventories",
        ],
        "unit": "RUB",
    },
]


_NUMBER_REGEX = re.compile(
    r"([-+]?\d[\d\s\u00A0]*[.,]?\d*)",
)


def _parse_number(raw: str) -> Optional[float]:
    """
    Преобразует строку с числом из отчёта в float.

    Учитывает пробелы как разделители тысяч и запятую/точку как разделитель дробной части.
    """
    cleaned = raw.replace("\u00A0", " ").replace(" ", "")
    if not cleaned:
        return None
    # Если есть и запятая, и точка, предполагаем, что точка — разделитель тысяч, а запятая — дробная часть.
    if "," in cleaned and "." in cleaned:
        # Удаляем точки-разделители тысяч, запятую заменяем на точку.
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        # Если только запятая — считаем её десятичным разделителем.
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_metrics(raw_text: str) -> list[Metric]:
    """
    Извлечение ключевых финансовых показателей из текста PDF-отчёта.

    Текущая реализация использует простые rule-based паттерны:
    - поиск строк, содержащих ключевые фразы (выручка, чистая прибыль, активы и т.п.);
    - из найденной строки берётся последнее числовое значение как целевое.

    В дальнейшем может быть расширена до полноценного парсинга многолетних таблиц.
    """
    if not raw_text.strip():
        return []

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    metrics: list[Metric] = []
    seen_keys: set[str] = set()

    for definition in _METRIC_DEFINITIONS:
        key = definition["key"]
        compiled_patterns = [
            re.compile(pattern, flags=re.IGNORECASE) for pattern in definition["patterns"]
        ]

        best_match_value: Optional[float] = None
        best_fragment: Optional[str] = None

        for line in lines:
            if not any(p.search(line) for p in compiled_patterns):
                continue

            numbers = _NUMBER_REGEX.findall(line)
            if not numbers:
                continue

            value = _parse_number(numbers[-1])
            if value is None:
                continue

            # Пока берём первое "достаточно хорошее" совпадение как основное.
            best_match_value = value
            best_fragment = line
            break

        if best_match_value is None or best_fragment is None:
            continue

        if key in seen_keys:
            # На уровне MVP ограничиваемся одним значением на показатель.
            continue

        seen_keys.add(key)

        metrics.append(
            Metric(
                name=definition["name"],
                value=best_match_value,
                unit=definition["unit"],
                year=None,  # Извлечение года будет доработано позже.
                confidence_score=0.8,
                source_fragment=best_fragment,
            ),
        )

    return metrics

