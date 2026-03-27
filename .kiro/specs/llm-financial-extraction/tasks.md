# Implementation Plan: LLM Financial Extraction

## Overview

Реализация LLM-based извлечения финансовых метрик из PDF-отчётов с fallback на существующий
regex/camelot-pipeline. Порядок реализации: промпты → основной модуль → настройки → интеграция
в pipeline → NLP → тесты → фикстуры → env.

## Tasks

- [x] 1. Создать `src/core/prompts.py` с LLM-промптами
  - Определить константу `LLM_EXTRACTION_PROMPT` (system-промпт для извлечения метрик):
    защита от prompt injection, список 15 целевых метрик с русскими/английскими синонимами,
    правила confidence_score (0.9/0.7/0.5), инструкция по единицам измерения,
    обработка OCR-артефактов, требование возвращать только JSON-массив без markdown-обёртки
  - Определить константу `LLM_ANALYSIS_PROMPT` (system-промпт для анализа рисков):
    требование ссылаться на числовые значения, российские нормативные пороги
    (current_ratio ≥ 1.5, roa ≥ 5%, equity_ratio ≥ 0.5), формат ответа
    `{"risks": [...], "key_factors": [...], "recommendations": [...]}`,
    инструкция возвращать пустые списки при null-коэффициентах
  - Оба промпта содержат явную инструкцию возвращать только валидный JSON без markdown-обёртки
  - _Requirements: 2.1–2.9, 5.1–5.5, 7.1–7.4_

- [-] 2. Реализовать `src/analysis/llm_extractor.py`
  - [x] 2.1 Реализовать `_normalize_number_str(value_str: str) -> float | None`
    - Удалять пробелы-разделители тысяч, заменять запятую на точку
    - Обрабатывать формат `"1.234.567,89"` → `1234567.89`
    - Применять суффиксы масштаба: `{"тыс": 1_000, "тысяч": 1_000, "млн": 1_000_000, "миллион": 1_000_000, "млрд": 1_000_000_000, "миллиард": 1_000_000_000}`
    - Возвращать `None` при невозможности парсинга
    - _Requirements: 8.6, 8.7_

  - [x] 2.2 Написать property-тест для `_normalize_number_str`
    - **Property 8: Нормализация числовых строк** — для любой строки с пробелами-разделителями и/или запятой как десятичным разделителем функция возвращает корректный `float`
    - **Property 9: Суффиксы масштаба** — для любой строки с суффиксом тыс/млн/млрд результат равен числу, умноженному на соответствующий коэффициент
    - **Validates: Requirements 8.6, 8.7**

  - [x] 2.3 Реализовать `_apply_anomaly_check(key: str, value: float, confidence: float) -> tuple[float, float]`
    - Проверять аномальные значения: выручка < 0, коэффициент ликвидности > 1000
    - При аномалии: `confidence = min(original, 0.3)`, логировать WARNING с аномальным значением
    - Возвращать `(value, adjusted_confidence)`
    - _Requirements: 8.8_

  - [x] 2.4 Написать property-тест для `_apply_anomaly_check`
    - **Property 10: Снижение confidence для аномальных значений** — для любого значения, выходящего за разумные пределы, функция возвращает `confidence ≤ 0.3`
    - **Validates: Requirements 8.8**

  - [x] 2.5 Реализовать `parse_llm_extraction_response(response: str) -> dict[str, ExtractionMetadata]`
    - Импортировать `ExtractionMetadata` из `src/analysis/pdf_extractor.py`
    - Извлекать JSON из markdown-блоков через regex `r"```+json\s*(.*?)\s*```+"` с флагом `re.DOTALL`
    - Обрабатывать оба формата: JSON-массив `[{...}]` и объект `{"metrics": [{...}]}`
    - При `JSONDecodeError` возвращать `{}` и логировать WARNING с первыми 200 символами ответа
    - Для каждой валидной метрики: вызывать `_normalize_number_str`, затем `_apply_anomaly_check`
    - Проверять значение через `_is_valid_financial_value()` из `pdf_extractor.py`; при провале — `value=None`
    - Создавать `ExtractionMetadata(value=..., confidence=confidence_score, source="llm")`
    - Для отсутствующих метрик из `_METRIC_KEYWORDS`: `ExtractionMetadata(None, 0.0, "derived")`
    - Гарантировать наличие всех 15 ключей из `_METRIC_KEYWORDS` в возвращаемом словаре
    - _Requirements: 1.3, 1.4, 1.5, 8.1–8.8_

  - [x] 2.6 Написать property-тест для `parse_llm_extraction_response`
    - **Property 2: Корректность ExtractionMetadata** — для любого валидного JSON-ответа LLM с ненулевым значением метрики функция создаёт `ExtractionMetadata` с `source="llm"` и `confidence` равным `confidence_score` из ответа
    - **Property 11: Markdown round-trip** — для любого валидного JSON-массива, обёрнутого в markdown-блок любого вида (≥3 обратных кавычки), функция возвращает тот же результат, что и для JSON без обёртки
    - **Validates: Requirements 1.3, 1.4, 8.2**

  - [x] 2.7 Реализовать `chunk_text(text, chunk_size=12_000, overlap=200, max_chunks=5) -> list[str]`
    - Если `len(text) ≤ chunk_size` → вернуть `[text]`
    - Разбивать по `"\n\n"`, жадно собирать абзацы в чанк до `chunk_size`
    - Следующий чанк начинается с последних `overlap` символов текущего
    - Останавливаться после `max_chunks` чанков
    - _Requirements: 3.1–3.5_

  - [x] 2.8 Написать property-тесты для `chunk_text`
    - **Property 3: Размер чанков** — для любого текста и `chunk_size` все чанки имеют длину ≤ `chunk_size`
    - **Property 4: Количество чанков** — для любого текста и `max_chunks` функция возвращает не более `max_chunks` элементов
    - **Property 5: Перекрытие чанков** — для любого текста длиннее `chunk_size` последние `overlap` символов первого чанка являются префиксом второго
    - **Validates: Requirements 3.1, 3.3, 3.5**

  - [x] 2.9 Реализовать `merge_extraction_results(results: list[dict[str, ExtractionMetadata]]) -> dict[str, ExtractionMetadata]`
    - Для каждого ключа из `_METRIC_KEYWORDS` выбирать `ExtractionMetadata` с наибольшим `confidence` среди всех чанков
    - Если нет ни одной записи с `value != None` → `ExtractionMetadata(None, 0.0, "derived")`
    - _Requirements: 3.4_

  - [x] 2.10 Написать property-тест для `merge_extraction_results`
    - **Property 6: Merge выбирает максимальный confidence** — для любого списка результатов чанков функция выбирает `ExtractionMetadata` с наибольшим `confidence` для каждой метрики
    - **Validates: Requirements 3.4**

  - [x] 2.11 Реализовать `extract_with_llm(text, ai_service, chunk_size, max_chunks, token_budget) -> dict[str, ExtractionMetadata] | None`
    - Импортировать `LLM_EXTRACTION_PROMPT` из `src/core/prompts.py`
    - **Первым делом** проверять `token_budget`: если `len(text) > token_budget` → логировать WARNING `"budget_exceeded"`, вернуть `None` (до вызова `chunk_text`)
    - Вызывать `chunk_text(text, chunk_size, max_chunks=max_chunks)`
    - Для каждого чанка оборачивать вызов в `try/except`:
      ```python
      try:
          response = await ai_service.invoke({"tool_input": chunk, "system": LLM_EXTRACTION_PROMPT})
      except Exception as e:
          logger.warning("LLM invoke error for chunk %d: %s", chunk_idx, repr(e))
          continue  # пропустить чанк, попробовать следующий
      ```
    - При `None` от `invoke()` — логировать WARNING и пропускать чанк (не прерывать весь процесс)
    - Вызывать `merge_extraction_results()` для объединения результатов всех чанков
    - Логировать структурированную запись: `extraction_method`, `metrics_extracted`, `confidence_avg`, `chunks_processed`, `chars_processed`
    - Возвращать `None` если ни один чанк не дал результата
    - _Requirements: 1.1, 1.2, 3.2, 3.3, 11.1, 11.2_

  - [x] 2.12 Написать property-тест для `extract_with_llm`
    - **Property 1: Полнота возвращаемого словаря** — для любого входного текста функция возвращает словарь ровно с 15 ключами из `_METRIC_KEYWORDS`, где каждое значение имеет тип `float` или `None`
    - **Validates: Requirements 1.1, 1.5, 10.1, 10.4**

- [x] 3. Checkpoint — убедиться что модуль `llm_extractor.py` корректен
  - Убедиться что все тесты проходят, спросить пользователя если есть вопросы.

- [x] 4. Добавить 4 новых поля в `src/models/settings.py`
  - Добавить поле `llm_extraction_enabled: bool = Field(False, alias="LLM_EXTRACTION_ENABLED")`
  - Добавить поле `llm_chunk_size: int = Field(12_000, alias="LLM_CHUNK_SIZE")` с `@field_validator`: диапазон 1000–50000, при нарушении — WARNING + default
  - Добавить поле `llm_max_chunks: int = Field(5, alias="LLM_MAX_CHUNKS")` с `@field_validator`: диапазон 1–20, при нарушении — WARNING + default
  - Добавить поле `llm_token_budget: int = Field(50_000, alias="LLM_TOKEN_BUDGET")` с `@field_validator`: диапазон 1000–200000, при нарушении — WARNING + default
  - _Requirements: 9.1–9.4_

- [x] 5. Интегрировать `_try_llm_extraction` в `src/tasks.py`
  - [x] 5.1 Реализовать `_try_llm_extraction(text, tables, logger) -> dict[str, ExtractionMetadata]`
    - Импортировать `extract_with_llm` из `src/analysis/llm_extractor.py`
    - Импортировать `ai_service` из `src/core/ai_service.py`
    - Если `not ai_service.is_configured` → логировать WARNING `"llm_unavailable"`, вернуть результат `parse_financial_statements_with_metadata`
    - Вызывать `await extract_with_llm(text, ai_service, chunk_size=app_settings.llm_chunk_size, max_chunks=app_settings.llm_max_chunks, token_budget=app_settings.llm_token_budget)`
    - Если результат `None` или исключение → логировать WARNING `"llm_error"`, вернуть fallback
    - Если ненулевых метрик < 3 → логировать WARNING с перечислением отсутствующих критических метрик (`revenue`, `total_assets`, `equity`), дополнить из fallback
    - Логировать причину переключения при каждом fallback
    - _Requirements: 4.1–4.5, 6.1–6.5, 11.2, 11.3_

  - [x] 5.2 Изменить `_run_extraction_phase()` для вызова `_try_llm_extraction`
    - После получения `text` и `tables` добавить ветку: если `app_settings.llm_extraction_enabled` → `metadata = await _try_llm_extraction(text, tables, logger)`, иначе → существующий вызов `parse_financial_statements_with_metadata`
    - Сохранить существующий интерфейс функции (входные параметры и возвращаемый словарь не меняются)
    - Результат `_try_llm_extraction` передаётся в `apply_confidence_filter()` так же, как и раньше
    - _Requirements: 6.1–6.5_

  - [x]* 5.3 Написать property-тест для `_run_extraction_phase`
    - **Property 12: Инвариант интерфейса `_run_extraction_phase()`** — для любого PDF-файла и значения флага `LLM_EXTRACTION_ENABLED` функция возвращает словарь с ключами `text`, `metrics`, `metadata`, `scanned`, `tables`
    - **Property 7: Fallback при ошибке LLM** — для любого типа исключения, выброшенного `ai_service.invoke()`, `_try_llm_extraction()` не выбрасывает исключение наружу и возвращает результат `parse_financial_statements_with_metadata`
    - **Validates: Requirements 4.2, 6.3**

- [x] 6. Обновить `src/analysis/nlp_analysis.py` для использования `LLM_ANALYSIS_PROMPT`
  - Добавить импорт: `from src.core.prompts import LLM_ANALYSIS_PROMPT`
  - Заменить inline-строку промпта в `analyze_narrative()` на `LLM_ANALYSIS_PROMPT`
  - Передавать промпт как `system`-поле: `ai_service.invoke({"tool_input": narrative_text, "system": LLM_ANALYSIS_PROMPT})`
  - _Requirements: 5.1–5.5, 7.2, 7.3_

- [x] 7. Checkpoint — убедиться что интеграция в pipeline работает
  - Убедиться что все тесты проходят, спросить пользователя если есть вопросы.

- [x] 8. Написать unit-тесты в `tests/test_llm_extractor.py`
  - [x] 8.1 Написать unit-тесты для `parse_llm_extraction_response`
    - `test_parse_json_array` — валидный JSON-массив `[...]`
    - `test_parse_json_object` — валидный JSON-объект `{"metrics": [...]}`
    - `test_parse_markdown_wrapped` — JSON в ` ```json ... ``` `
    - `test_parse_invalid_json` — невалидный JSON → `{}` + лог WARNING
    - `test_parse_empty_response` — пустая строка `""` → `{}` + лог WARNING, без исключения
    - `test_normalize_spaces_comma` — `"1 234,5"` → `1234.5`
    - `test_normalize_dots_comma` — `"1.234.567,89"` → `1234567.89`
    - `test_normalize_suffix_mln` — `"1,5 млн"` → `1500000.0`
    - `test_normalize_suffix_tys` — `"500 тыс"` → `500000.0`
    - `test_anomaly_reduces_confidence` — аномальное значение → `confidence ≤ 0.3`
    - Использовать `unittest.mock.AsyncMock` для мокирования `ai_service.invoke()`
    - _Requirements: 12.1_

  - [x] 8.2 Написать `test_llm_extractor_fallback`
    - Мокировать `ai_service.invoke()` возвращающим `None`
    - Проверить что `extract_with_llm()` возвращает пустой словарь без исключений
    - _Requirements: 12.2_

  - [x] 8.3 Написать `test_chunker_split` и `test_chunker_short_text`
    - `test_chunker_split`: текст > `chunk_size`, проверить границы по `\n\n`, перекрытие 200 символов, соблюдение `max_chunks`
    - `test_chunker_short_text`: текст ≤ `chunk_size` → один чанк
    - _Requirements: 12.3_

  - [x] 8.4 Написать `test_extraction_pipeline_with_llm_mock`
    - Мокировать `ai_service.invoke()` через `AsyncMock` с валидным JSON-ответом
    - Проверить интеграцию `_run_extraction_phase()` с `LLM_EXTRACTION_ENABLED=true`
    - Проверить что возвращаемый словарь содержит ключи `text`, `metrics`, `metadata`, `scanned`, `tables`
    - _Requirements: 12.4, 12.5_

- [x] 9. Создать fixture-файлы в `tests/data/llm_responses/`
  - Создать `tests/data/llm_responses/valid_array.json` — валидный JSON-массив с 10 метриками
  - Создать `tests/data/llm_responses/valid_object.json` — валидный JSON-объект `{"metrics": [...]}`
  - Создать `tests/data/llm_responses/markdown_wrapped.json` — JSON в ` ```json ... ``` ` блоке
  - Создать `tests/data/llm_responses/invalid_json.txt` — невалидный JSON (текст с ошибками)
  - Создать `tests/data/llm_responses/partial_metrics.json` — только 2 метрики (тест fallback-дополнения)
  - _Requirements: 12.6_

- [x] 10. Обновить `.env.example` с новыми переменными
  - Добавить секцию `# LLM Extraction` с четырьмя переменными:
    `LLM_EXTRACTION_ENABLED=false`, `LLM_CHUNK_SIZE=12000`, `LLM_MAX_CHUNKS=5`, `LLM_TOKEN_BUDGET=50000`
  - Добавить комментарии на русском языке для каждой переменной
  - _Requirements: 9.5_

- [x] 11. Финальный checkpoint — убедиться что все тесты проходят
  - Убедиться что все тесты проходят, спросить пользователя если есть вопросы.

## Notes

- Задачи с `*` опциональны и могут быть пропущены для ускорения MVP
- Property-тесты используют Hypothesis (`@given`, `@settings(max_examples=100)`)
- Все LLM-вызовы только через `src/core/ai_service.py` — прямой импорт агентов запрещён
- `src/analysis/llm_extractor.py` не импортирует FastAPI/SQLAlchemy (правило AGENTS.md)
- Логирование только через `logger = logging.getLogger(__name__)`, `%`-форматирование
