# Qwen Regression Fixes 2 — Bugfix Design

## Overview

Набор из 10 подтверждённых регрессионных багов в NeoFin AI, затрагивающих модули
`pdf_extractor.py`, `nlp_analysis.py`, `ratios.py` и `recommendations.py`.

Баги охватывают три категории:
- **Парсинг чисел** (БАГ 1, 2): некорректная обработка Unicode-минуса с пробелами и ложная фильтрация 4-значных финансовых значений как РСБУ-кодов
- **Логика AI-вызовов** (БАГ 3, 4, 7, 8): отправка пустого текста в LLM, неограниченный OCR-цикл, дублирование рекомендаций, недостаточный таймаут
- **Форматирование и стандарты** (БАГ 5, 6, 9, 10): утечка неизвестных ключей на фронтенд, неправильное форматирование отрицательных чисел, f-строки в логах

Стратегия исправления: минимальные точечные изменения в каждом файле без рефакторинга несвязанной логики.

---

## Glossary

- **Bug_Condition (C)**: Условие, при котором проявляется баг — конкретный входной сигнал или состояние системы, воспроизводящее дефект
- **Property (P)**: Ожидаемое корректное поведение при выполнении Bug_Condition
- **Preservation**: Существующее поведение, которое не должно измениться после исправления
- **isBugCondition**: Псевдокод-функция, формально описывающая условие проявления бага
- **_normalize_number**: Функция в `pdf_extractor.py`, конвертирующая строку в float с учётом русских форматов чисел
- **_extract_first_numeric_cell**: Функция в `pdf_extractor.py`, возвращающая первое числовое значение из списка ячеек таблицы, пропуская РСБУ-коды строк
- **extract_text_from_scanned**: Функция в `pdf_extractor.py`, выполняющая OCR постранично через pytesseract
- **analyze_narrative**: Функция в `nlp_analysis.py`, отправляющая текст пояснительной записки в LLM для NLP-анализа
- **translate_ratios**: Функция в `ratios.py`, транслирующая русские ключи коэффициентов в snake_case English для фронтенда
- **_format_metric_value**: Функция в `recommendations.py`, форматирующая числовое значение для отображения в рекомендациях
- **_parse_recommendations_response**: Функция в `recommendations.py`, парсящая JSON-ответ LLM и извлекающая список рекомендаций
- **generate_recommendations**: Async-функция в `recommendations.py`, вызывающая AI-сервис для генерации рекомендаций
- **_log_missing_data**: Функция в `ratios.py`, логирующая отсутствующие финансовые поля
- **RATIO_KEY_MAP**: Словарь в `ratios.py`, маппирующий русские ключи коэффициентов в English snake_case
- **MAX_OCR_PAGES**: Константа-лимит страниц OCR, которую необходимо добавить в `pdf_extractor.py`

---

## Bug Details

### Bug Condition

Баги проявляются в 10 независимых местах кодовой базы. Каждый баг имеет свою Bug_Condition.

**Формальная спецификация (сводная):**

```
FUNCTION isBugCondition(context)
  INPUT: context — описание текущего состояния системы
  OUTPUT: boolean

  -- БАГ 1: Unicode-минус с пробелами в _normalize_number
  IF context.file == "pdf_extractor.py"
     AND context.function == "_normalize_number"
     AND context.raw_value CONTAINS unicode_minus_or_dash
     AND context.raw_value CONTAINS whitespace
     AND cleaned_after_re_sub(context.raw_value) IN {"", "-", "."}
     AND cleaned_after_strip(context.raw_value) == "-"
  THEN RETURN True

  -- БАГ 2: 4-значная строка без разделителей в _extract_first_numeric_cell
  IF context.file == "pdf_extractor.py"
     AND context.function == "_extract_first_numeric_cell"
     AND context.cell_str.replace(" ","").isdigit()
     AND len(context.cell_str.replace(" ","")) == 4
     AND context.cell_str NOT CONTAINS separator(" ", ",", ".")
  THEN RETURN True

  -- БАГ 3: пустой текст в analyze_narrative
  IF context.file == "nlp_analysis.py"
     AND context.function == "analyze_narrative"
     AND clean_for_llm(context.full_text) == ""
     AND _extract_narrative("") == ""
     AND ai_service.invoke IS CALLED WITH empty_string
  THEN RETURN True

  -- БАГ 4: неограниченный OCR в extract_text_from_scanned
  IF context.file == "pdf_extractor.py"
     AND context.function == "extract_text_from_scanned"
     AND context.pdf_page_count > 50
     AND context.pages_processed > 50
  THEN RETURN True

  -- БАГ 5: неизвестный ключ в translate_ratios
  IF context.file == "ratios.py"
     AND context.function == "translate_ratios"
     AND context.ratio_key NOT IN RATIO_KEY_MAP
     AND context.ratio_key IN result_dict
  THEN RETURN True

  -- БАГ 6: отрицательное значение в _format_metric_value
  IF context.file == "recommendations.py"
     AND context.function == "_format_metric_value"
     AND isinstance(context.value, float)
     AND context.value < -100
     AND "," NOT IN formatted_result
  THEN RETURN True

  -- БАГ 7: дубликаты в _parse_recommendations_response
  IF context.file == "recommendations.py"
     AND context.function == "_parse_recommendations_response"
     AND context.llm_recommendations CONTAINS duplicates
     AND len(result) > len(set(result))
  THEN RETURN True

  -- БАГ 8: таймаут 60с в generate_recommendations
  IF context.file == "recommendations.py"
     AND context.function == "generate_recommendations"
     AND context.ai_service_timeout == 60
     AND context.base_agent_has_retry == True
  THEN RETURN True

  -- БАГ 9: f-строки в _log_missing_data (ratios.py)
  IF context.file == "ratios.py"
     AND context.function == "_log_missing_data"
     AND "f\"" IN logger_call OR "f'" IN logger_call
  THEN RETURN True

  -- БАГ 10: f-строки в _parse_recommendations_response (recommendations.py)
  IF context.file == "recommendations.py"
     AND context.function == "_parse_recommendations_response"
     AND "f\"" IN logger_call OR "f'" IN logger_call
  THEN RETURN True

  RETURN False
END FUNCTION
```

### Примеры проявления багов

- **БАГ 1**: Строка `" - 12 345"` → после `re.sub(r"[^0-9.\-]", "", ...)` получается `"-12345"`, но если строка `" - "` (только минус с пробелами) → `cleaned = "-"` → `cleaned in {"", "-", "."}` → `return None` вместо отрицательного числа. Ожидается: `cleaned.strip()` перед проверкой.
- **БАГ 2**: Ячейка `"1000"` (тысяча рублей) → `digits_only = "1000"`, `len == 4`, `isdigit() == True` → пропускается как РСБУ-код. Ожидается: принять как финансовое значение. Ячейка `"2110"` (РСБУ-код) → корректно пропускается.
- **БАГ 3**: `clean_for_llm(text)` возвращает `""` → `_extract_narrative("")` возвращает `""` → `narrative_text = ""` → `ai_service.invoke(input={"tool_input": ""})` — пустой запрос в LLM. Ожидается: `if not cleaned_text: return _empty_result()`.
- **БАГ 4**: PDF на 200 страниц → `while True` без ограничения → 200 вызовов pytesseract → зависание на 30+ минут. Ожидается: остановка после `MAX_OCR_PAGES = 50`.
- **БАГ 5**: `calculate_ratios` возвращает ключ `"Долг/Выручка"`, отсутствующий в `RATIO_KEY_MAP` → `translate_ratios` пробрасывает его на фронтенд → фронтенд не умеет обрабатывать русский ключ. Ожидается: дропать ключ, логировать предупреждение.
- **БАГ 6**: `_format_metric_value(-500_000_000.0)` → `value < 0.1` False, `value > 100` False (т.к. -500M < 0) → `return f"{value:.2f}"` → `"-500000000.00"` без разделителей. Ожидается: `"-500,000,000"`.
- **БАГ 7**: LLM возвращает `["Оптимизировать ликвидность", "Оптимизировать ликвидность", "Снизить долг"]` → результат содержит дубликат. Ожидается: `["Оптимизировать ликвидность", "Снизить долг"]`.
- **БАГ 8**: `BaseAIAgent` делает до 3 retry с экспоненциальной задержкой → суммарное время может превысить 60с → `TimeoutError` до получения ответа. Ожидается: `timeout=90`.
- **БАГ 9**: `logger.warning(f"Missing critical financial field: {field}")` → нарушение AGENTS.md. Ожидается: `logger.warning("Missing critical financial field: %s", field)`.
- **БАГ 10**: `logger.warning(f"Failed to parse recommendations JSON: {e}")` → нарушение AGENTS.md. Ожидается: `logger.warning("Failed to parse recommendations JSON: %s", e)`.

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Строки с корректным отрицательным числом без пробелов (`"-12345"`) продолжают возвращать корректный float
- Ячейки с 5+ цифрами (`"12345"`, `"123456"`) продолжают парситься как финансовые значения
- РСБУ-коды из 1–3 цифр (`"66"`, `"110"`) продолжают пропускаться
- `analyze_narrative` с непустым текстом продолжает передавать его в LLM
- PDF с ≤ 50 страницами продолжают обрабатываться полностью через OCR
- Все ключи, присутствующие в `RATIO_KEY_MAP`, продолжают транслироваться корректно
- Положительные значения > 100 продолжают форматироваться с разделителями тысяч
- Уникальные рекомендации от LLM продолжают возвращаться без изменений
- `generate_recommendations` при успешном ответе в пределах таймаута продолжает возвращать список рекомендаций
- `calculate_ratios` с полным набором данных продолжает возвращать все 13 коэффициентов корректно

**Scope:**
Все входные данные, не попадающие под Bug_Condition, должны быть полностью не затронуты исправлениями. Это включает:
- Строки с числами без Unicode-минуса и пробелов
- Ячейки таблиц с 1–3 или 5+ цифрами
- Непустой текст для NLP-анализа
- PDF с небольшим числом страниц
- Словари коэффициентов с известными ключами

---

## Hypothesized Root Cause

### БАГ 1 — `_normalize_number` в `pdf_extractor.py`
Строка вида `" - "` (пробел-минус-пробел, без цифр): `negative=True` (содержит `-`) → `cleaned = re.sub(r"[^0-9.\-]", "", " - ")` → `"-"` → `cleaned in {"-"}` → `return None`. Исправление: добавить `cleaned = cleaned.strip()` перед проверкой `if cleaned in {"", "-", "."}` — но поскольку `re.sub` уже убирает пробелы, реальный сценарий: строка `"- "` после `replace(" ", "")` даёт `"-"`. Корень: проверка `cleaned in {"", "-", "."}` должна выполняться после `strip()` на случай остаточных пробелов от других замен.

### БАГ 2 — `_extract_first_numeric_cell` в `pdf_extractor.py`
Условие `digits_only.isdigit() and len(digits_only) <= 4` отбрасывает все строки из ровно 4 цифр без разделителей. Это корректно для РСБУ-кодов (`"2110"`, `"1600"`), но ошибочно для финансовых значений в тысячах рублей (`"1000"`, `"9999"`). Исправление: сузить условие до `len(digits_only) <= 3` — РСБУ-коды строк всегда 4-значные, а 4-значные финансовые значения (тысячи рублей) должны приниматься.

### БАГ 3 — `analyze_narrative` в `nlp_analysis.py`
После `cleaned_text = clean_for_llm(full_text)` нет проверки на пустую строку. При пустом `cleaned_text`: `_extract_narrative("")` возвращает `""` → `if not narrative_text: narrative_text = cleaned_text` → `narrative_text = ""` → LLM вызывается с пустым текстом. Исправление: добавить `if not cleaned_text: return _empty_result()` после вызова `clean_for_llm`.

### БАГ 4 — `extract_text_from_scanned` в `pdf_extractor.py`
Цикл `while True` с инкрементом `page_num` не имеет верхней границы. Для PDF с 200 страницами это означает 200 вызовов pytesseract. Исправление: добавить константу `MAX_OCR_PAGES = 50` и условие `if page_num > MAX_OCR_PAGES: break`.

### БАГ 5 — `translate_ratios` в `ratios.py`
В ветке `else` (ключ не найден в `RATIO_KEY_MAP`) код делает `result[k] = v` — пробрасывает оригинальный русский ключ на фронтенд. Исправление: убрать `result[k] = v`, оставить только логирование.

### БАГ 6 — `_format_metric_value` в `recommendations.py`
Условие `elif value > 100` не срабатывает для отрицательных чисел (`-500_000_000 > 100` — False). Функция падает в ветку `else: return f"{value:.2f}"` без разделителей тысяч. Исправление: заменить `value > 100` на `abs(value) > 100`.

### БАГ 7 — `_parse_recommendations_response` в `recommendations.py`
После извлечения списка из JSON нет дедупликации. Исправление: применить `list(dict.fromkeys(result))` для дедупликации с сохранением порядка.

### БАГ 8 — `generate_recommendations` в `recommendations.py`
`BaseAIAgent` реализует exponential retry (до 3 попыток). При `timeout=60` суммарное время 3 попыток с задержками может превысить 60с. Исправление: увеличить `timeout=90`.

### БАГ 9 — `_log_missing_data` в `ratios.py`
f-строки в `logger.warning(f"...")` и `logger.debug(f"...")` нарушают стандарт AGENTS.md. Исправление: заменить на %-форматирование.

### БАГ 10 — `_parse_recommendations_response` в `recommendations.py`
f-строки в `logger.warning(f"...")` нарушают стандарт AGENTS.md. Исправление: заменить на %-форматирование.

---

## Correctness Properties

Property 1: Bug Condition — Unicode-минус и пробелы в _normalize_number

_For any_ строки `raw_value`, где после `re.sub(r"[^0-9.\-]", "", ...)` результат равен `"-"` (только минус без цифр), но исходная строка содержала цифры (т.е. `negative=True` и цифры присутствовали до очистки), исправленная `_normalize_number` SHALL применять `cleaned.strip()` перед проверкой `if cleaned in {"", "-", "."}` и корректно возвращать отрицательное float-значение.

**Validates: Requirements 2.1, 3.1**

Property 2: Bug Condition — 4-значные ячейки в _extract_first_numeric_cell

_For any_ ячейки таблицы, содержащей ровно 4 цифры без разделителей (например `"1000"`, `"9999"`), исправленная `_extract_first_numeric_cell` SHALL возвращать числовое значение (не пропускать как РСБУ-код). Для ячеек с 1–3 цифрами функция SHALL продолжать возвращать `None`.

**Validates: Requirements 2.2, 3.2, 3.3**

Property 3: Bug Condition — Пустой текст в analyze_narrative

_For any_ вызова `analyze_narrative(full_text)`, где `clean_for_llm(full_text)` возвращает пустую строку, исправленная функция SHALL возвращать `_empty_result()` без вызова `ai_service.invoke`.

**Validates: Requirements 2.3, 3.4**

Property 4: Bug Condition — Лимит страниц OCR в extract_text_from_scanned

_For any_ PDF с количеством страниц N, исправленная `extract_text_from_scanned` SHALL обрабатывать не более `min(N, MAX_OCR_PAGES)` страниц, где `MAX_OCR_PAGES = 50`. Для PDF с N ≤ 50 SHALL обрабатываться все страницы без пропусков.

**Validates: Requirements 2.4, 3.5**

Property 5: Bug Condition — Неизвестные ключи в translate_ratios

_For any_ словаря `ratios`, содержащего ключ, отсутствующий в `RATIO_KEY_MAP`, исправленная `translate_ratios` SHALL не включать этот ключ в возвращаемый словарь. Для всех ключей, присутствующих в `RATIO_KEY_MAP`, функция SHALL продолжать возвращать полный словарь с English-ключами.

**Validates: Requirements 2.5, 3.6**

Property 6: Bug Condition — Форматирование отрицательных чисел в _format_metric_value

_For any_ значения `value` типа `float`, где `abs(value) > 100`, исправленная `_format_metric_value` SHALL возвращать строку с разделителями тысяч (`,`). Это применяется как к положительным, так и к отрицательным значениям.

**Validates: Requirements 2.6, 3.7**

Property 7: Bug Condition — Дедупликация рекомендаций в _parse_recommendations_response

_For any_ списка рекомендаций от LLM, содержащего дубликаты, исправленная `_parse_recommendations_response` SHALL возвращать список с уникальными элементами, сохраняя порядок первого вхождения. Для списка без дубликатов функция SHALL возвращать его без изменений.

**Validates: Requirements 2.7, 3.8**

Property 8: Preservation — Таймаут generate_recommendations

_For any_ вызова `generate_recommendations`, исправленная функция SHALL использовать `timeout=90` при вызове `ai_service.invoke`. При успешном завершении в пределах таймаута функция SHALL продолжать возвращать список рекомендаций.

**Validates: Requirements 2.8, 3.9**

Property 9: Preservation — %-форматирование в логах

_For any_ вызова `_log_missing_data` в `ratios.py` и `_parse_recommendations_response` в `recommendations.py`, все вызовы `logger.*()` SHALL использовать %-форматирование (не f-строки). Логическое поведение функций SHALL оставаться неизменным.

**Validates: Requirements 2.9, 2.10, 3.10**

---

## Fix Implementation

### Changes Required

#### БАГ 1 — `src/analysis/pdf_extractor.py`, `_normalize_number`

```python
# БЫЛО:
cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
if cleaned in {"", "-", "."}:
    return None

# СТАЛО:
cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
cleaned = cleaned.strip()
if cleaned in {"", "-", "."}:
    return None
```

#### БАГ 2 — `src/analysis/pdf_extractor.py`, `_extract_first_numeric_cell`

```python
# БЫЛО:
if digits_only.isdigit() and len(digits_only) <= 4:
    continue

# СТАЛО:
if digits_only.isdigit() and len(digits_only) <= 3:
    continue
```

#### БАГ 3 — `src/analysis/nlp_analysis.py`, `analyze_narrative`

```python
# БЫЛО:
cleaned_text = clean_for_llm(full_text)
narrative_text = _extract_narrative(cleaned_text)

# СТАЛО:
cleaned_text = clean_for_llm(full_text)
if not cleaned_text:
    return _empty_result()
narrative_text = _extract_narrative(cleaned_text)
```

#### БАГ 4 — `src/analysis/pdf_extractor.py`, `extract_text_from_scanned`

```python
MAX_OCR_PAGES = 50  # константа на уровне модуля

# В начале цикла while True:
if page_num > MAX_OCR_PAGES:
    logger.warning("OCR page limit reached (%d pages), stopping", MAX_OCR_PAGES)
    break
```

#### БАГ 5 — `src/analysis/ratios.py`, `translate_ratios`

```python
# БЫЛО:
else:
    unknown_keys.append(k)
    result[k] = v

# СТАЛО:
else:
    unknown_keys.append(k)
```

#### БАГ 6 — `src/analysis/recommendations.py`, `_format_metric_value`

```python
# БЫЛО:
elif value > 100:
    return f"{value:,.0f}"

# СТАЛО:
elif abs(value) > 100:
    return f"{value:,.0f}"
```

#### БАГ 7 — `src/analysis/recommendations.py`, `_parse_recommendations_response`

```python
# БЫЛО:
result = [str(r).strip() for r in recommendations if r]

# СТАЛО:
result = list(dict.fromkeys(str(r).strip() for r in recommendations if r))
```

#### БАГ 8 — `src/analysis/recommendations.py`, `generate_recommendations`

```python
# БЫЛО:
response = await ai_service.invoke(input={...}, timeout=60)

# СТАЛО:
response = await ai_service.invoke(input={...}, timeout=90)
```

#### БАГ 9 — `src/analysis/ratios.py`, `_log_missing_data`

```python
# БЫЛО:
logger.warning(f"Missing critical financial field: {field}")
logger.debug(f"Optional field not available: {field}")

# СТАЛО:
logger.warning("Missing critical financial field: %s", field)
logger.debug("Optional field not available: %s", field)
```

#### БАГ 10 — `src/analysis/recommendations.py`, `_parse_recommendations_response`

```python
# БЫЛО:
logger.warning(f"Failed to parse recommendations JSON: {e}")
logger.warning(f"Generated only {len(result)} recommendations, expected 3-5")

# СТАЛО:
logger.warning("Failed to parse recommendations JSON: %s", e)
logger.warning("Generated only %d recommendations, expected 3-5", len(result))
```
