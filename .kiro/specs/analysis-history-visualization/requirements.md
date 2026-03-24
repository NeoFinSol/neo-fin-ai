# Требования: analysis-history-visualization

## Введение

Этап 3 доработки NeoFin AI под конкурс. Система уже умеет принимать PDF-отчёты, вычислять 5 финансовых коэффициентов, строить интегральный скоринг 0–100 и генерировать NLP-рекомендации. Текущая проблема: история анализов хранится только в `localStorage` (mockHistory), реальных API-вызовов нет; графики коэффициентов в `DetailedReport.tsx` используют захардкоженные данные; для демо на конкурсе нужна маскировка реальных числовых значений.

Данная спецификация охватывает четыре направления:
1. **AnalysisHistory API** — эндпоинты `GET /analyses` и `GET /analyses/{task_id}` на backend.
2. **Frontend AnalysisHistory** — подключение к реальному API вместо localStorage/mockHistory.
3. **Маскировка данных** — скрытие реальных чисел в публичных ответах для демо-режима.
4. **Визуализация коэффициентов** — графики на странице `DetailedReport.tsx` на основе реальных данных.

---

## Глоссарий

- **Analysis** — запись в таблице `analyses` (PostgreSQL): `task_id`, `status`, `result` (JSONB), `created_at`.
- **AnalysisHistory_API** — backend-слой FastAPI, предоставляющий список и детали анализов.
- **AnalysisHistory_Page** — React-страница `AnalysisHistory.tsx`, отображающая список анализов.
- **DetailedReport_Page** — React-страница `DetailedReport.tsx`, отображающая полный отчёт по одному анализу.
- **Masking_Service** — компонент backend, заменяющий реальные числовые значения на маскированные при активном демо-режиме.
- **Demo_Mode** — режим работы системы, активируемый переменной окружения `DEMO_MODE=1`, при котором числовые данные маскируются.
- **Pagination** — механизм постраничной выдачи списка анализов: параметры `page` (номер страницы, начиная с 1) и `page_size` (количество записей на странице).
- **HistoryEntry** — объект истории на frontend: `id`, `filename`, `date`, `score`, `riskLevel`, `result`.
- **RatioChart** — график коэффициентов на странице `DetailedReport_Page`, построенный на основе реальных значений из `AnalysisData.ratios`.
- **CRUD** — модуль `src/db/crud.py`, единственное место с SQL-операциями.
- **X-API-Key** — заголовок аутентификации для всех защищённых эндпоинтов.

---

## Требования

### Требование 1: Эндпоинт списка анализов

**User Story:** Как разработчик frontend, я хочу получать список завершённых анализов через API, чтобы отображать реальную историю вместо mockHistory.

#### Критерии приёмки

1. THE **AnalysisHistory_API** SHALL предоставлять эндпоинт `GET /analyses`, защищённый заголовком `X-API-Key`.
2. WHEN запрос `GET /analyses` получен с валидным `X-API-Key`, THE **AnalysisHistory_API** SHALL возвращать JSON-объект со структурой `{ items: AnalysisSummary[], total: int, page: int, page_size: int }`.
3. THE **AnalysisHistory_API** SHALL принимать query-параметры `page` (целое число ≥ 1, по умолчанию 1) и `page_size` (целое число от 1 до 100, по умолчанию 20).
4. THE **AnalysisHistory_API** SHALL возвращать в каждом элементе `items` поля: `task_id` (string), `status` (string), `created_at` (ISO 8601 datetime), `score` (float или null), `risk_level` (string или null), `filename` (string или null).
5. THE **AnalysisHistory_API** SHALL сортировать результаты по `created_at` в порядке убывания (новые — первыми).
6. IF параметр `page` или `page_size` содержит нечисловое значение, THEN THE **AnalysisHistory_API** SHALL возвращать HTTP 422 с описанием ошибки валидации.
7. IF параметр `page_size` превышает 100, THEN THE **AnalysisHistory_API** SHALL возвращать HTTP 422 с сообщением о превышении лимита.
8. THE **CRUD** SHALL предоставлять функцию `get_analyses_list(page, page_size)`, возвращающую кортеж `(items: list[Analysis], total: int)`, используя `SELECT ... ORDER BY created_at DESC LIMIT ... OFFSET ...`.

---

### Требование 2: Эндпоинт деталей анализа

**User Story:** Как разработчик frontend, я хочу получать полные данные конкретного анализа по `task_id`, чтобы отображать детальный отчёт из истории.

#### Критерии приёмки

1. THE **AnalysisHistory_API** SHALL предоставлять эндпоинт `GET /analyses/{task_id}`, защищённый заголовком `X-API-Key`.
2. WHEN запрос `GET /analyses/{task_id}` получен с валидным `X-API-Key` и существующим `task_id`, THE **AnalysisHistory_API** SHALL возвращать полный объект анализа: `task_id`, `status`, `created_at`, и поле `data` с полным содержимым `result` из БД.
3. IF `task_id` не найден в базе данных, THEN THE **AnalysisHistory_API** SHALL возвращать HTTP 404 с сообщением `"Analysis not found"`.
4. IF запрос выполнен без заголовка `X-API-Key` или с невалидным ключом, THEN THE **AnalysisHistory_API** SHALL возвращать HTTP 401 или HTTP 403.
5. THE **AnalysisHistory_API** SHALL повторно использовать существующую функцию `get_analysis(task_id)` из модуля **CRUD** без дублирования SQL-логики.

---

### Требование 3: Подключение frontend к реальному API

**User Story:** Как пользователь, я хочу видеть реальную историю анализов из базы данных, а не данные из localStorage, чтобы история сохранялась между сессиями и устройствами.

#### Критерии приёмки

1. THE **AnalysisHistory_Page** SHALL загружать список анализов через вызов `GET /analyses` при монтировании компонента.
2. WHILE данные загружаются, THE **AnalysisHistory_Page** SHALL отображать индикатор загрузки (skeleton или spinner).
3. IF запрос к `GET /analyses` завершился ошибкой, THEN THE **AnalysisHistory_Page** SHALL отображать сообщение об ошибке с кнопкой повторной попытки.
4. THE **AnalysisHistory_Page** SHALL отображать пагинацию, позволяющую переходить между страницами при `total > page_size`.
5. WHEN пользователь нажимает на строку анализа, THE **AnalysisHistory_Page** SHALL загружать детали через `GET /analyses/{task_id}` и отображать `DetailedReport_Page`.
6. THE **AnalysisHistory_Page** SHALL отображать поля: имя файла (`filename`), дату (`created_at` в формате `DD.MM.YYYY`), скоринг (`score`), уровень риска (`risk_level`).
7. IF поле `score` или `risk_level` равно `null` (анализ в статусе `processing` или `failed`), THEN THE **AnalysisHistory_Page** SHALL отображать `—` вместо числового значения.
8. THE **AnalysisHistory_Page** SHALL использовать `axios`-клиент из `frontend/src/api/client.ts` с заголовком `X-API-Key` для всех запросов к API истории.
9. THE **AnalysisHistory_Page** SHALL прекратить использование `localStorage` и `HistoryContext` как источника данных для отображения списка; `HistoryContext.addEntry` может продолжать использоваться для добавления новых записей после завершения анализа.

---

### Требование 4: Маскировка данных в демо-режиме

**User Story:** Как организатор демонстрации на конкурсе, я хочу скрывать реальные числовые значения клиентских данных в публичных ответах API, чтобы не раскрывать конфиденциальную финансовую информацию.

#### Критерии приёмки

1. WHERE переменная окружения `DEMO_MODE=1`, THE **Masking_Service** SHALL заменять все числовые значения в полях `metrics` и `ratios` ответа API на маскированные значения.
2. THE **Masking_Service** SHALL заменять числовые значения по следующему правилу: сохранять знак и порядок величины, но заменять значащие цифры на `X` в строковом представлении (например, `1234567.89` → `"X,XXX,XXX"`, `0.85` → `"X.XX"`).
3. WHERE переменная окружения `DEMO_MODE=1`, THE **Masking_Service** SHALL заменять значения в поле `text` (извлечённый текст PDF) на строку `"[DEMO: текст скрыт]"`.
4. WHERE переменная окружения `DEMO_MODE=1`, THE **Masking_Service** SHALL сохранять без изменений: `score` (интегральный скоринг), `risk_level`, `factors`, `normalized_scores`, `nlp` (риски и рекомендации).
5. IF переменная окружения `DEMO_MODE` не установлена или равна `0`, THEN THE **Masking_Service** SHALL возвращать данные без изменений.
6. THE **Masking_Service** SHALL применяться в роутере `GET /result/{task_id}` и в новых эндпоинтах `GET /analyses` и `GET /analyses/{task_id}` — после чтения из БД, до отправки ответа клиенту.
7. THE **Masking_Service** SHALL быть реализован как чистая функция `mask_analysis_data(data: dict, demo_mode: bool) -> dict` в отдельном модуле `src/utils/masking.py`.
8. FOR ALL входных словарей `data`, вызов `mask_analysis_data(mask_analysis_data(data, True), True)` SHALL возвращать результат, эквивалентный однократному вызову `mask_analysis_data(data, True)` (идемпотентность маскировки).

---

### Требование 5: Визуализация коэффициентов

**User Story:** Как пользователь, я хочу видеть графики финансовых коэффициентов на странице детального отчёта, построенные на основе реальных данных текущего анализа, чтобы наглядно оценить финансовое состояние компании.

#### Критерии приёмки

1. THE **DetailedReport_Page** SHALL отображать столбчатую диаграмму (BarChart) всех доступных коэффициентов из `AnalysisData.ratios` с ненулевыми значениями.
2. THE **DetailedReport_Page** SHALL строить данные для графиков исключительно из полей объекта `AnalysisData.ratios`, переданного в компонент через props, без использования захардкоженных значений.
3. WHEN поле `AnalysisData.ratios` содержит менее двух ненулевых коэффициентов, THE **DetailedReport_Page** SHALL отображать сообщение `"Недостаточно данных для построения графика"` вместо пустого графика.
4. THE **DetailedReport_Page** SHALL отображать подписи осей на русском языке, используя словарь маппинга EN-ключей в человекочитаемые русские названия (например, `current_ratio` → `"Тек. ликвидность"`, `roa` → `"ROA"`, `roe` → `"ROE"`).
5. THE **DetailedReport_Page** SHALL использовать компонент `BarChart` из библиотеки `@mantine/charts` (уже установлена в проекте) для отображения коэффициентов.
6. THE **DetailedReport_Page** SHALL отображать значения коэффициентов с точностью до двух знаков после запятой в tooltip графика.
7. WHEN значение коэффициента превышает отраслевой норматив (пороговые значения: `current_ratio ≥ 2.0`, `quick_ratio ≥ 1.0`, `roa ≥ 0.05`, `roe ≥ 0.10`, `equity_ratio ≥ 0.5`), THE **DetailedReport_Page** SHALL отображать столбец зелёным цветом (`teal.6`); в противном случае — красным (`red.5`).
8. THE **DetailedReport_Page** SHALL удалить захардкоженные значения `historicalData` (массив с фиктивными данными за 2023–2025 годы) и заменить их на данные из реального `AnalysisData.ratios`.

---

### Требование 6: Парсинг и сериализация данных истории

**User Story:** Как разработчик, я хочу иметь надёжный контракт данных между backend и frontend для истории анализов, чтобы исключить ошибки типизации и несоответствия полей.

#### Критерии приёмки

1. THE **AnalysisHistory_API** SHALL использовать Pydantic v2 схему `AnalysisSummaryResponse` для сериализации каждого элемента списка `GET /analyses`, содержащую поля: `task_id: str`, `status: str`, `created_at: datetime`, `score: float | None`, `risk_level: str | None`, `filename: str | None`.
2. THE **AnalysisHistory_API** SHALL использовать Pydantic v2 схему `AnalysisListResponse` для сериализации ответа `GET /analyses`, содержащую поля: `items: list[AnalysisSummaryResponse]`, `total: int`, `page: int`, `page_size: int`.
3. THE **AnalysisHistory_API** SHALL использовать Pydantic v2 схему `AnalysisDetailResponse` для сериализации ответа `GET /analyses/{task_id}`, содержащую поля: `task_id: str`, `status: str`, `created_at: datetime`, `data: dict | None`.
4. THE **AnalysisHistory_Page** SHALL использовать TypeScript-интерфейсы `AnalysisSummary` и `AnalysisListResponse`, добавленные в `frontend/src/api/interfaces.ts`, для типизации ответов API истории.
5. FOR ALL объектов `AnalysisSummaryResponse`, сериализованных backend и десериализованных frontend, поле `created_at` SHALL быть корректно распознано как строка ISO 8601 и отформатировано в `DD.MM.YYYY` на стороне frontend без потери данных (round-trip свойство).
