# Implementation Plan

## Фаза 0 — Exploratory тесты (воспроизвести баги ДО исправления)

- [x] 1. Write bug condition exploration tests
  - **Property 1: Bug Condition** - Qwen Regression Bugs 2
  - **CRITICAL**: Эти тесты ДОЛЖНЫ ПАДАТЬ на незафиксированном коде — падение подтверждает существование багов
  - **DO NOT attempt to fix the tests or the code when they fail**
  - **GOAL**: Воспроизвести баги и задокументировать контрпримеры
  - **Scoped PBT Approach**: Для детерминированных багов — конкретные входные данные
  - Написать `tests/test_qwen_regression_exploratory_2.py`:
    - `test_normalize_number_unicode_minus_with_spaces`: `_normalize_number(" - ")` → ожидать `None` (баг: должно возвращать `None` только для строк без цифр, но сейчас `" - 12345"` тоже может упасть)
    - `test_extract_first_numeric_cell_skips_4digit`: `_extract_first_numeric_cell(["1000"])` → ожидать `None` (баг: 4-значное число пропускается как РСБУ-код)
    - `test_analyze_narrative_empty_text_calls_llm`: замокать `ai_service.invoke`, вызвать `analyze_narrative("")` с `clean_for_llm` возвращающим `""` → убедиться, что `ai_service.invoke` вызывается с пустой строкой (баг)
    - `test_ocr_no_page_limit`: убедиться, что `extract_text_from_scanned` не имеет константы `MAX_OCR_PAGES` (баг: нет ограничения)
    - `test_translate_ratios_unknown_key_leaks`: `translate_ratios({"НеизвестныйКлюч": 1.0})` → убедиться, что `"НеизвестныйКлюч"` присутствует в результате (баг: утечка на фронтенд)
    - `test_format_metric_value_negative_large`: `_format_metric_value(-500_000_000.0)` → убедиться, что `","` отсутствует в результате (баг: нет разделителей тысяч)
    - `test_parse_recommendations_duplicates`: `_parse_recommendations_response('{"recommendations": ["A", "A", "B"]}')` → убедиться, что результат содержит дубликат `"A"` (баг)
    - `test_generate_recommendations_timeout_60`: проверить исходный код `recommendations.py` на наличие `timeout=60` (баг: должно быть 90)
    - `test_log_missing_data_uses_fstrings`: проверить исходный код `ratios.py` на наличие f-строк в `_log_missing_data` (баг: нарушение AGENTS.md)
    - `test_parse_recommendations_uses_fstrings`: проверить исходный код `recommendations.py` на наличие f-строк в `_parse_recommendations_response` (баг: нарушение AGENTS.md)
  - Запустить тесты на незафиксированном коде
  - **EXPECTED OUTCOME**: Тесты ПАДАЮТ (это правильно — подтверждает существование багов)
  - Задокументировать контрпримеры для понимания root cause
  - Отметить задачу выполненной когда тесты написаны, запущены и падение задокументировано
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10_


## Фаза 1 — Preservation тесты (ПЕРЕД исправлением)

- [x] 2. Write preservation property tests (BEFORE implementing fixes)
  - **Property 2: Preservation** - Existing Behavior Unchanged
  - **IMPORTANT**: Следовать observation-first методологии
  - Наблюдать поведение незафиксированного кода для входных данных, НЕ попадающих под Bug_Condition
  - Написать `tests/test_qwen_regression_preservation_2.py`:
    - `prop_normalize_number_valid_negatives`: для всех строк вида `"-{digits}"` без пробелов — `_normalize_number` возвращает корректный отрицательный float (Hypothesis)
    - `prop_extract_numeric_cell_5plus_digits`: для всех строк с 5+ цифрами без разделителей — `_extract_first_numeric_cell` возвращает числовое значение (Hypothesis)
    - `test_extract_numeric_cell_1_3_digits_skipped`: `_extract_first_numeric_cell(["66"])`, `_extract_first_numeric_cell(["110"])` → `None` (РСБУ-коды 1–3 цифры пропускаются)
    - `test_analyze_narrative_nonempty_calls_llm`: замокать `ai_service.invoke`, вызвать `analyze_narrative("текст отчёта")` → убедиться, что `ai_service.invoke` вызывается (непустой текст передаётся в LLM)
    - `test_ocr_processes_all_pages_under_limit`: убедиться, что для PDF с ≤ 50 страниц все страницы обрабатываются (нет преждевременной остановки)
    - `prop_translate_ratios_known_keys`: для любого словаря с ключами только из `RATIO_KEY_MAP` — `translate_ratios` возвращает полный словарь с English-ключами (Hypothesis)
    - `test_format_metric_value_positive_large`: `_format_metric_value(500_000_000.0)` → содержит `","` (положительные большие числа форматируются корректно)
    - `prop_parse_recommendations_unique`: для любого списка уникальных рекомендаций — `_parse_recommendations_response` возвращает их без изменений (Hypothesis)
    - `test_generate_recommendations_success_returns_list`: при успешном ответе AI — `generate_recommendations` возвращает список строк
    - `test_calculate_ratios_full_data`: `calculate_ratios` с полным набором данных возвращает все 13 коэффициентов
  - Запустить тесты на незафиксированном коде
  - **EXPECTED OUTCOME**: Тесты ПРОХОДЯТ (подтверждает baseline-поведение для сохранения)
  - Отметить задачу выполненной когда тесты написаны, запущены и проходят на незафиксированном коде
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10_


## Группа 1 — Парсинг чисел (БАГ 1–2)

- [x] 3. Fix БАГ 1 — pdf_extractor.py: Unicode-минус с пробелами в _normalize_number

  - [x] 3.1 Добавить `cleaned.strip()` перед проверкой пустой строки в `src/analysis/pdf_extractor.py`
    - Найти строку `if cleaned in {"", "-", "."}:` в функции `_normalize_number`
    - Добавить `cleaned = cleaned.strip()` непосредственно перед этой проверкой
    - Убедиться, что `re.sub` вызывается до `strip()` (порядок: re.sub → strip → проверка)
    - _Bug_Condition: isBugCondition where cleaned_after_re_sub == "-" (Unicode-минус с пробелами)_
    - _Expected_Behavior: cleaned.strip() перед проверкой; строки без цифр возвращают None корректно_
    - _Preservation: строки вида "-12345" продолжают возвращать корректный отрицательный float_
    - _Requirements: 2.1, 3.1_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Unicode Minus Fix
    - **IMPORTANT**: Перезапустить ТЕСТ ИЗ ЗАДАЧИ 1 — не писать новый тест
    - Запустить `test_normalize_number_unicode_minus_with_spaces` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (подтверждает исправление бага)
    - _Requirements: 2.1_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Valid Negative Numbers
    - **IMPORTANT**: Перезапустить ТЕСТЫ ИЗ ЗАДАЧИ 2 — не писать новые тесты
    - Запустить `prop_normalize_number_valid_negatives` из задачи 2
    - **EXPECTED OUTCOME**: Тесты ПРОХОДЯТ (нет регрессий)

- [x] 4. Fix БАГ 2 — pdf_extractor.py: 4-значные ячейки пропускаются как РСБУ-коды

  - [x] 4.1 Изменить условие фильтрации с `<= 4` на `<= 3` в `_extract_first_numeric_cell`
    - Найти условие `if digits_only.isdigit() and len(digits_only) <= 4:` в `_extract_first_numeric_cell`
    - Заменить `<= 4` на `<= 3`
    - РСБУ-коды строк всегда 4-значные (2110, 1600 и т.д.) — они теперь НЕ будут пропускаться этим условием, но будут обрабатываться через `_LINE_CODE_MAP` в Strategy A
    - _Bug_Condition: isBugCondition where cell_str has exactly 4 digits without separators_
    - _Expected_Behavior: 4-значные строки без разделителей принимаются как финансовые значения_
    - _Preservation: ячейки с 1–3 цифрами продолжают пропускаться; 5+ цифр принимаются_
    - _Requirements: 2.2, 3.2, 3.3_

  - [x] 4.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - 4-Digit Cell Fix
    - Запустить `test_extract_first_numeric_cell_skips_4digit` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (`_extract_first_numeric_cell(["1000"])` возвращает значение)
    - _Requirements: 2.2_

  - [x] 4.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Numeric Cell Parsing
    - Запустить `prop_extract_numeric_cell_5plus_digits` и `test_extract_numeric_cell_1_3_digits_skipped` из задачи 2
    - **EXPECTED OUTCOME**: Тесты ПРОХОДЯТ (нет регрессий)


## Группа 2 — Логика AI-вызовов (БАГ 3–4)

- [x] 5. Fix БАГ 3 — nlp_analysis.py: пустой текст отправляется в LLM

  - [x] 5.1 Добавить ранний возврат при пустом `cleaned_text` в `analyze_narrative`
    - Найти строку `cleaned_text = clean_for_llm(full_text)` в `src/analysis/nlp_analysis.py`
    - Добавить сразу после неё: `if not cleaned_text: return _empty_result()`
    - Убедиться, что `_extract_narrative` вызывается только при непустом `cleaned_text`
    - _Bug_Condition: isBugCondition where clean_for_llm returns "" AND ai_service.invoke called with ""_
    - _Expected_Behavior: if not cleaned_text: return _empty_result() без вызова LLM_
    - _Preservation: непустой cleaned_text продолжает передаваться в _extract_narrative и далее в LLM_
    - _Requirements: 2.3, 3.4_

  - [x] 5.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Empty Text Guard
    - Запустить `test_analyze_narrative_empty_text_calls_llm` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (ai_service.invoke НЕ вызывается при пустом тексте)
    - _Requirements: 2.3_

  - [x] 5.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-Empty Text Passes to LLM
    - Запустить `test_analyze_narrative_nonempty_calls_llm` из задачи 2
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (нет регрессий)

- [x] 6. Fix БАГ 4 — pdf_extractor.py: неограниченный OCR-цикл

  - [x] 6.1 Добавить константу `MAX_OCR_PAGES = 50` и ограничение цикла в `extract_text_from_scanned`
    - Добавить константу `MAX_OCR_PAGES = 50` на уровне модуля в `src/analysis/pdf_extractor.py` (рядом с другими константами)
    - В начале тела цикла `while True:` в `extract_text_from_scanned` добавить:
      ```python
      if page_num > MAX_OCR_PAGES:
          logger.warning("OCR page limit reached (%d pages), stopping", MAX_OCR_PAGES)
          break
      ```
    - Убедиться, что проверка выполняется ДО вызова `convert_from_path`
    - _Bug_Condition: isBugCondition where pdf_page_count > 50 AND pages_processed > 50_
    - _Expected_Behavior: остановка после MAX_OCR_PAGES=50 страниц с warning в логах_
    - _Preservation: PDF с <= 50 страницами обрабатываются полностью без пропусков_
    - _Requirements: 2.4, 3.5_

  - [x] 6.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - OCR Page Limit
    - Запустить `test_ocr_no_page_limit` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (константа `MAX_OCR_PAGES` существует и равна 50)
    - _Requirements: 2.4_

  - [x] 6.3 Verify preservation tests still pass
    - **Property 2: Preservation** - OCR Under Limit
    - Запустить `test_ocr_processes_all_pages_under_limit` из задачи 2
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (нет регрессий)


## Группа 3 — Форматирование и стандарты (БАГ 5–8)

- [x] 7. Fix БАГ 5 — ratios.py: утечка неизвестных ключей на фронтенд

  - [x] 7.1 Убрать `result[k] = v` для неизвестных ключей в `translate_ratios`
    - Найти ветку `else:` в `translate_ratios` в `src/analysis/ratios.py`
    - Удалить строку `result[k] = v` из ветки `else`
    - Оставить только `unknown_keys.append(k)` (логирование уже есть)
    - _Bug_Condition: isBugCondition where ratio_key NOT IN RATIO_KEY_MAP AND ratio_key IN result_dict_
    - _Expected_Behavior: неизвестные ключи дропаются из результата, логируется warning_
    - _Preservation: все ключи из RATIO_KEY_MAP транслируются корректно в полный словарь_
    - _Requirements: 2.5, 3.6_

  - [x] 7.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Unknown Key Dropped
    - Запустить `test_translate_ratios_unknown_key_leaks` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (неизвестный ключ отсутствует в результате)
    - _Requirements: 2.5_

  - [x] 7.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Known Keys Translated
    - Запустить `prop_translate_ratios_known_keys` из задачи 2
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (нет регрессий)

- [x] 8. Fix БАГ 6 — recommendations.py: форматирование отрицательных чисел

  - [x] 8.1 Заменить `value > 100` на `abs(value) > 100` в `_format_metric_value`
    - Найти условие `elif value > 100:` в `_format_metric_value` в `src/analysis/recommendations.py`
    - Заменить на `elif abs(value) > 100:`
    - _Bug_Condition: isBugCondition where isinstance(value, float) AND value < -100 AND "," NOT IN result_
    - _Expected_Behavior: abs(value) > 100 — форматирование с разделителями тысяч для любого знака_
    - _Preservation: положительные значения > 100 продолжают форматироваться с разделителями_
    - _Requirements: 2.6, 3.7_

  - [x] 8.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Negative Large Number Format
    - Запустить `test_format_metric_value_negative_large` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (`_format_metric_value(-500_000_000.0)` содержит `","`)
    - _Requirements: 2.6_

  - [x] 8.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Positive Large Number Format
    - Запустить `test_format_metric_value_positive_large` из задачи 2
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (нет регрессий)

- [x] 9. Fix БАГ 7 — recommendations.py: дублирование рекомендаций

  - [x] 9.1 Применить дедупликацию с сохранением порядка в `_parse_recommendations_response`
    - Найти строку `result = [str(r).strip() for r in recommendations if r]` в `src/analysis/recommendations.py`
    - Заменить на `result = list(dict.fromkeys(str(r).strip() for r in recommendations if r))`
    - _Bug_Condition: isBugCondition where llm_recommendations CONTAINS duplicates AND len(result) > len(set(result))_
    - _Expected_Behavior: дедупликация с сохранением порядка первого вхождения_
    - _Preservation: уникальные рекомендации возвращаются без изменений_
    - _Requirements: 2.7, 3.8_

  - [x] 9.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Deduplication
    - Запустить `test_parse_recommendations_duplicates` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (дубликаты удалены, порядок сохранён)
    - _Requirements: 2.7_

  - [x] 9.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Unique Recommendations Unchanged
    - Запустить `prop_parse_recommendations_unique` из задачи 2
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (нет регрессий)

- [x] 10. Fix БАГ 8 — recommendations.py: таймаут 60с -> 90с

  - [x] 10.1 Увеличить `timeout` с 60 до 90 в `generate_recommendations`
    - Найти `timeout=60` в вызове `ai_service.invoke` в `generate_recommendations` в `src/analysis/recommendations.py`
    - Заменить на `timeout=90`
    - Обновить сообщение в `except asyncio.TimeoutError`: `logger.warning("Recommendations generation timed out (90s)")`
    - _Bug_Condition: isBugCondition where ai_service_timeout == 60 AND base_agent_has_retry == True_
    - _Expected_Behavior: timeout=90 обеспечивает достаточное время при retry в BaseAIAgent_
    - _Preservation: при успешном ответе в пределах таймаута возвращается список рекомендаций_
    - _Requirements: 2.8, 3.9_

  - [x] 10.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Timeout 90s
    - Запустить `test_generate_recommendations_timeout_60` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (в коде `timeout=90`, не 60)
    - _Requirements: 2.8_

  - [x] 10.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Recommendations Success Path
    - Запустить `test_generate_recommendations_success_returns_list` из задачи 2
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (нет регрессий)


## Группа 4 — Стандарт логирования (БАГ 9–10)

- [x] 11. Fix БАГ 9 — ratios.py: f-строки в _log_missing_data

  - [x] 11.1 Заменить f-строки на %-форматирование в `_log_missing_data` в `src/analysis/ratios.py`
    - Заменить `logger.warning(f"Missing critical financial field: {field}")` на `logger.warning("Missing critical financial field: %s", field)`
    - Заменить `logger.debug(f"Optional field not available: {field}")` на `logger.debug("Optional field not available: %s", field)`
    - _Bug_Condition: isBugCondition where f-string used in logger call in _log_missing_data_
    - _Expected_Behavior: %-форматирование во всех logger.*() вызовах в _log_missing_data_
    - _Preservation: логическое поведение функции остаётся неизменным; calculate_ratios работает корректно_
    - _Requirements: 2.9, 3.10_

  - [x] 11.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - No F-Strings in ratios.py
    - Запустить `test_log_missing_data_uses_fstrings` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (f-строки отсутствуют в `_log_missing_data`)
    - _Requirements: 2.9_

  - [x] 11.3 Verify preservation tests still pass
    - **Property 2: Preservation** - calculate_ratios Full Data
    - Запустить `test_calculate_ratios_full_data` из задачи 2
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (нет регрессий)

- [x] 12. Fix БАГ 10 — recommendations.py: f-строки в _parse_recommendations_response

  - [x] 12.1 Заменить f-строки на %-форматирование в `_parse_recommendations_response` в `src/analysis/recommendations.py`
    - Заменить `logger.warning(f"Failed to parse recommendations JSON: {e}")` на `logger.warning("Failed to parse recommendations JSON: %s", e)`
    - Заменить `logger.warning(f"Generated only {len(result)} recommendations, expected 3-5")` на `logger.warning("Generated only %d recommendations, expected 3-5", len(result))`
    - Проверить все остальные `logger.*()` вызовы в функции на наличие f-строк
    - _Bug_Condition: isBugCondition where f-string used in logger call in _parse_recommendations_response_
    - _Expected_Behavior: %-форматирование во всех logger.*() вызовах в _parse_recommendations_response_
    - _Preservation: логическое поведение парсинга остаётся неизменным_
    - _Requirements: 2.10, 3.10_

  - [x] 12.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - No F-Strings in recommendations.py
    - Запустить `test_parse_recommendations_uses_fstrings` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (f-строки отсутствуют в `_parse_recommendations_response`)
    - _Requirements: 2.10_

  - [x] 12.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Recommendations Parsing
    - Запустить `prop_parse_recommendations_unique` из задачи 2
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (нет регрессий)


## Checkpoint

- [x] 13. Checkpoint — Ensure all tests pass
  - Запустить полный набор тестов: `pytest tests/test_qwen_regression_exploratory_2.py tests/test_qwen_regression_preservation_2.py -v`
  - Запустить регрессионные тесты: `pytest tests/ -v --tb=short -x`
  - Убедиться, что все тесты проходят, включая ранее написанные в `test_qwen_regression_fixes.py` и `test_qwen_regression_preservation.py`
  - Если возникают вопросы — уточнить у пользователя
