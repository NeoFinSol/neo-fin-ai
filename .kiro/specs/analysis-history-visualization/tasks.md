# План реализации: analysis-history-visualization

## Обзор

Реализация четырёх направлений: backend API истории анализов (`GET /analyses`, `GET /analyses/{task_id}`), модуль маскировки данных для демо-режима, подключение frontend к реальному API вместо localStorage/mockHistory, улучшение визуализации коэффициентов в `DetailedReport.tsx`.

## Задачи

- [-] 1. Модуль маскировки данных
  - [x] 1.1 Создать `src/utils/masking.py` с чистой функцией `mask_analysis_data(data, demo_mode)`
    - Реализовать замену числовых значений в `data["data"]["metrics"]` и `data["data"]["ratios"]` на строки-маски при `demo_mode=True`
    - Формат маски: сохранять знак и порядок величины, заменять значащие цифры на `X` (например, `1234567.89` → `"X,XXX,XXX"`, `0.85` → `"X.XX"`, `-42.1` → `"-XX.X"`)
    - Заменять `data["data"]["text"]` на `"[DEMO: текст скрыт]"` при `demo_mode=True`
    - Сохранять без изменений: `score`, `risk_level`, `factors`, `normalized_scores`, `nlp`
    - При `demo_mode=False` возвращать данные без изменений (identity)
    - Без импортов FastAPI/SQLAlchemy — только стандартная библиотека
    - _Требования: 4.1, 4.2, 4.3, 4.4, 4.5, 4.7_

  - [x] 1.2 Написать property-тест: Property 5 — маскировка числовых значений
    - **Property 5: Маскировка числовых значений**
    - **Validates: Requirements 4.1, 4.4**
    - Файл: `tests/test_masking.py`
    - `@given(analysis_data_strategy())` + `@settings(max_examples=100)`
    - Проверить: все числовые значения в `metrics` и `ratios` заменены на нечисловые; `score`, `risk_level`, `factors`, `normalized_scores`, `nlp` идентичны исходным

  - [x] 1.3 Написать property-тест: Property 6 — identity при demo_mode=False
    - **Property 6: Identity при demo_mode=False**
    - **Validates: Requirements 4.5**
    - Файл: `tests/test_masking.py`
    - `@given(analysis_data_strategy())` + `@settings(max_examples=100)`
    - Проверить: `mask_analysis_data(data, False) == data`

  - [x] 1.4 Написать property-тест: Property 7 — идемпотентность маскировки
    - **Property 7: Идемпотентность маскировки**
    - **Validates: Requirements 4.8**
    - Файл: `tests/test_masking.py`
    - `@given(analysis_data_strategy())` + `@settings(max_examples=100)`
    - Проверить: `mask_analysis_data(mask_analysis_data(data, True), True) == mask_analysis_data(data, True)`

  - [x] 1.5 Написать unit-тесты для `mask_analysis_data`
    - `mask_analysis_data({}, False)` → `{}`
    - `mask_analysis_data` с пустыми `metrics`/`ratios` → без ошибок
    - Файл: `tests/test_masking.py`
    - _Требования: 4.5, 4.7_

- [ ] 2. CRUD: функция `get_analyses_list`
  - [x] 2.1 Добавить `get_analyses_list(page, page_size)` в `src/db/crud.py`
    - `SELECT ... FROM analyses ORDER BY created_at DESC LIMIT page_size OFFSET (page-1)*page_size`
    - Параллельный `SELECT COUNT(*) FROM analyses` для получения `total`
    - Возвращать `tuple[list[Analysis], int]`
    - _Требования: 1.8_

  - [x] 2.2 Написать property-тест: Property 3 — корректность пагинации CRUD
    - **Property 3: Корректность пагинации CRUD**
    - **Validates: Requirements 1.3, 1.8**
    - Файл: `tests/test_crud_analyses.py`
    - `@given(st.integers(min_value=1, max_value=10), st.integers(min_value=1, max_value=100), st.lists(analysis_strategy(), min_size=0, max_size=200))` + `@settings(max_examples=100)`
    - Проверить: `total` равен общему числу записей, `len(items) <= page_size`

  - [x] 2.3 Написать unit-тесты для `get_analyses_list`
    - Пустая БД → `([], 0)`
    - Одна запись → `([item], 1)`
    - Страница за пределами данных → `([], total)`
    - Файл: `tests/test_crud_analyses.py`
    - _Требования: 1.8_

- [ ] 3. Pydantic v2 схемы и TypeScript-интерфейсы
  - [x] 3.1 Добавить три схемы в `src/models/schemas.py`
    - `AnalysisSummaryResponse`: `task_id: str`, `status: str`, `created_at: datetime`, `score: float | None`, `risk_level: str | None`, `filename: str | None`
    - `AnalysisListResponse`: `items: list[AnalysisSummaryResponse]`, `total: int`, `page: int`, `page_size: int`
    - `AnalysisDetailResponse`: `task_id: str`, `status: str`, `created_at: datetime`, `data: dict | None`
    - _Требования: 6.1, 6.2, 6.3_

  - [x] 3.2 Добавить два интерфейса в `frontend/src/api/interfaces.ts`
    - `AnalysisSummary`: `task_id`, `status`, `created_at: string` (ISO 8601), `score: number | null`, `risk_level: string | null`, `filename: string | null`
    - `AnalysisListResponse`: `items: AnalysisSummary[]`, `total: number`, `page: number`, `page_size: number`
    - _Требования: 6.4_

- [ ] 4. Роутер `src/routers/analyses.py` и подключение в `src/app.py`
  - [x] 4.1 Создать `src/routers/analyses.py` с двумя эндпоинтами
    - `GET /analyses`: `page: int = 1`, `page_size: int = Query(20, le=100)`, `Depends(get_api_key)`
      - Вызвать `get_analyses_list(page, page_size)`
      - Для каждого элемента извлечь `score`, `risk_level`, `filename` из `analysis.result`
      - Применить `mask_analysis_data` если `DEMO_MODE=1`
      - Вернуть `AnalysisListResponse`
    - `GET /analyses/{task_id}`: `Depends(get_api_key)`
      - Вызвать `get_analysis(task_id)`, при `None` → 404 `"Analysis not found"`
      - Применить `mask_analysis_data` если `DEMO_MODE=1`
      - Вернуть `AnalysisDetailResponse`
    - _Требования: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 4.2 Подключить роутер в `src/app.py`
    - Добавить `import src.routers.analyses as analyses_router`
    - Добавить `app.include_router(analyses_router.router)` по аналогии с существующими роутерами
    - _Требования: 1.1, 2.1_

  - [x] 4.3 Применить `mask_analysis_data` в `src/routers/result.py`
    - После чтения из БД, до отправки ответа — применить маскировку при `DEMO_MODE=1`
    - _Требования: 4.6_

- [x] 5. Checkpoint — убедиться, что все backend-тесты проходят
  - Убедиться, что все тесты проходят, задать вопросы пользователю при необходимости.

- [ ] 6. Тесты backend: роутер `/analyses`
  - [ ] 6.1 Написать unit-тесты для `GET /analyses` и `GET /analyses/{task_id}`
    - `GET /analyses` без `X-API-Key` → 401/403
    - `GET /analyses/{task_id}` с несуществующим `task_id` → 404
    - `GET /analyses?page=abc` → 422
    - `GET /analyses?page_size=101` → 422
    - Файл: `tests/test_analyses_router.py`
    - _Требования: 1.6, 1.7, 2.3, 2.4_

  - [ ]* 6.2 Написать property-тест: Property 1 — структура ответа GET /analyses
    - **Property 1: Структура ответа GET /analyses**
    - **Validates: Requirements 1.2, 1.4**
    - Файл: `tests/test_analyses_router.py`
    - `@given(st.lists(analysis_strategy(), min_size=0, max_size=50))` + `@settings(max_examples=100)`
    - Проверить: ответ содержит `items`, `total`, `page`, `page_size`; каждый элемент содержит `task_id`, `status`, `created_at`, `score`, `risk_level`, `filename`

  - [ ]* 6.3 Написать property-тест: Property 2 — сортировка по created_at DESC
    - **Property 2: Сортировка по created_at DESC**
    - **Validates: Requirements 1.5**
    - Файл: `tests/test_analyses_router.py`
    - `@given(st.lists(analysis_strategy(), min_size=2, max_size=20))` + `@settings(max_examples=100)`
    - Проверить: `items[i].created_at >= items[i+1].created_at` для всех i

  - [ ]* 6.4 Написать property-тест: Property 4 — round-trip GET /analyses/{task_id}
    - **Property 4: Round-trip GET /analyses/{task_id}**
    - **Validates: Requirements 2.2**
    - Файл: `tests/test_analyses_router.py`
    - `@given(analysis_strategy())` + `@settings(max_examples=100)`
    - Проверить: `task_id`, `status`, `data` в ответе совпадают с исходными значениями в БД

- [ ] 7. Frontend: `AnalysisHistory.tsx` — подключение к реальному API
  - [ ] 7.1 Переписать `frontend/src/pages/AnalysisHistory.tsx`
    - Убрать `useHistory` / `HistoryContext` как источник данных для отображения списка
    - Добавить состояния: `loading`, `error`, `items: AnalysisSummary[]`, `total`, `page`
    - `useEffect` при монтировании и смене `page` → `GET /analyses?page=X&page_size=20` через `client.ts`
    - Skeleton-индикатор при `loading=true` (компонент `Skeleton` из Mantine)
    - Сообщение об ошибке + кнопка "Повторить" при ошибке запроса
    - Пагинация через `Pagination` из Mantine при `total > page_size`
    - При клике на строку → `GET /analyses/{task_id}` → передать `data` в `DetailedReport`
    - Отображать `"—"` для `null` `score` и `risk_level`
    - Форматировать `created_at` (ISO 8601) в `DD.MM.YYYY`
    - _Требования: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

  - [ ]* 7.2 Написать unit-тесты для `AnalysisHistory`
    - При монтировании делает вызов к `GET /analyses`
    - Отображает skeleton при `loading=true`
    - Отображает ошибку + кнопку "Повторить" при ошибке API
    - Отображает пагинацию при `total > page_size`
    - Отображает `"—"` для `null` `score` и `risk_level`
    - Файл: `frontend/src/pages/__tests__/AnalysisHistory.test.tsx`
    - _Требования: 3.1, 3.2, 3.3, 3.4, 3.7_

  - [ ]* 7.3 Написать property-тест: Property 10 — round-trip форматирования даты
    - **Property 10: Round-trip форматирования даты**
    - **Validates: Requirements 3.6, 6.5**
    - Файл: `frontend/src/pages/__tests__/AnalysisHistory.test.tsx`
    - `fc.assert(fc.property(isoDateArbitrary, ...), { numRuns: 100 })`
    - Проверить: `formatDate(isoDate)` возвращает `DD.MM.YYYY`, день/месяц/год совпадают с исходными

- [ ] 8. Frontend: `DetailedReport.tsx` — BarChart из реальных ratios
  - [ ] 8.1 Переработать секцию визуализации в `frontend/src/pages/DetailedReport.tsx`
    - Удалить `historicalData` (захардкоженный массив за 2023–2025)
    - Создать вспомогательную функцию `buildChartData(ratios)`: фильтровать ненулевые значения, применять словарь маппинга EN-ключей → русские названия
    - Словарь маппинга: `current_ratio` → `"Тек. ликвидность"`, `quick_ratio` → `"Быстрая ликв."`, `roa` → `"ROA"`, `roe` → `"ROE"`, `equity_ratio` → `"Автономия"` и т.д.
    - Создать вспомогательную функцию `getBarColor(key, value)`: `teal.6` если `value >= THRESHOLDS[key]`, иначе `red.5`
    - Пороги: `current_ratio: 2.0`, `quick_ratio: 1.0`, `roa: 0.05`, `roe: 0.10`, `equity_ratio: 0.5`
    - При < 2 ненулевых коэффициентов — отображать `"Недостаточно данных для построения графика"` вместо `BarChart`
    - Заменить `LineChart` с `historicalData` на `BarChart` с реальными данными из `result.ratios`
    - _Требования: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [ ]* 8.2 Написать property-тест: Property 8 — данные BarChart из реальных ratios
    - **Property 8: Данные BarChart из реальных ratios**
    - **Validates: Requirements 5.1, 5.2**
    - Файл: `frontend/src/pages/__tests__/DetailedReport.test.tsx`
    - `fc.assert(fc.property(ratiosArbitrary, ...), { numRuns: 100 })`
    - Проверить: `buildChartData(ratios).length === nonZeroCount`

  - [ ]* 8.3 Написать property-тест: Property 9 — цветовое кодирование столбцов
    - **Property 9: Цветовое кодирование столбцов**
    - **Validates: Requirements 5.7**
    - Файл: `frontend/src/pages/__tests__/DetailedReport.test.tsx`
    - `fc.assert(fc.property(ratioWithThresholdArbitrary, ...), { numRuns: 100 })`
    - Проверить: `getBarColor(key, value) === (value >= threshold ? 'teal.6' : 'red.5')`

  - [ ]* 8.4 Написать unit-тест: < 2 ненулевых коэффициентов → "Недостаточно данных"
    - Файл: `frontend/src/pages/__tests__/DetailedReport.test.tsx`
    - _Требования: 5.3_

- [ ] 9. Финальный checkpoint — убедиться, что все тесты проходят
  - Убедиться, что все тесты проходят (backend + frontend), задать вопросы пользователю при необходимости.

## Примечания

- Задачи, отмеченные `*`, опциональны и могут быть пропущены для ускорения MVP
- Каждая задача ссылается на конкретные требования для трассируемости
- Property-тесты используют `hypothesis` (Python) и `fast-check` (TypeScript)
- Маскировка применяется во всех трёх эндпоинтах: `GET /result/{task_id}`, `GET /analyses`, `GET /analyses/{task_id}`
- `filename` извлекается из `result["filename"]` — изменение схемы БД не требуется
