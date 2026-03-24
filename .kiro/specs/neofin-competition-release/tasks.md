# Tasks: NeoFin Competition Release

## Task Overview

Реализация фичи `neofin-competition-release` разбита на 5 групп задач, соответствующих 5 требованиям. Порядок выполнения: Requirement 1 → Requirement 2 → Requirement 3 → Requirement 4 → Requirement 5.

---

## Requirement 1: Confidence Score и Explainability

### Task 1.1: Расширить `pdf_extractor.py` — добавить ExtractionMetadata

- [ ] Добавить `ExtractionSource = Literal["table_exact", "table_partial", "text_regex", "derived"]`
- [ ] Добавить `@dataclass class ExtractionMetadata` с полями `value`, `confidence`, `source`
- [ ] Реализовать `determine_source()` по шкале: `table_exact`→0.9, `table_partial`→0.7, `text_regex`→0.5, `derived`→0.3
- [ ] Реализовать `parse_financial_statements_with_metadata(tables, text) -> dict[str, ExtractionMetadata]`
- [ ] Обновить `parse_financial_statements()` — вызывать `with_metadata` и возвращать `{k: v.value}` (обратная совместимость)
- [ ] Для показателей не найденных в PDF: `ExtractionMetadata(value=None, confidence=0.0, source="derived")`

**Затронутые файлы:** `src/analysis/pdf_extractor.py`

---

### Task 1.2: Добавить фильтрацию по confidence в `tasks.py`

- [ ] Добавить `CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))`
- [ ] Реализовать `_apply_confidence_filter(metadata, threshold) -> tuple[dict[str, float|None], dict[str, dict]]`
- [ ] Обновить `process_pdf()`: вызывать `parse_financial_statements_with_metadata()` → `_apply_confidence_filter()` → передавать `filtered_metrics` в `calculate_ratios()`
- [ ] Добавить `extraction_metadata` в payload перед `update_analysis()`

**Затронутые файлы:** `src/tasks.py`

---

### Task 1.3: Добавить новые Pydantic-схемы и настройки

- [ ] Добавить `ExtractionMetadataItem(BaseModel)` с полями `confidence: float = Field(ge=0.0, le=1.0)`, `source: Literal[...]`
- [ ] Добавить `extraction_metadata: dict[str, ExtractionMetadataItem] | None` в схему ответа анализа
- [ ] Добавить `CONFIDENCE_THRESHOLD` в `src/models/settings.py`

**Затронутые файлы:** `src/models/schemas.py`, `src/models/settings.py`

---

### Task 1.4: Обновить `frontend/src/api/interfaces.ts`

- [ ] Добавить `ExtractionSource` type
- [ ] Добавить `ExtractionMetadataItem` interface
- [ ] Добавить `extraction_metadata?: Record<string, ExtractionMetadataItem>` в `AnalysisData`

**Затронутые файлы:** `frontend/src/api/interfaces.ts`

---

### Task 1.5: Реализовать компонент `ConfidenceBadge.tsx`

- [ ] Создать `frontend/src/components/ConfidenceBadge.tsx`
- [ ] Цветовая логика: `> 0.8` → 🟢, `0.5–0.8` → 🟡, `< 0.5` → 🔴
- [ ] Tooltip: «Источник», «Метод», «Уверенность» в структурированном виде
- [ ] Приглушённый стиль строки при `confidence < threshold`

**Затронутые файлы:** `frontend/src/components/ConfidenceBadge.tsx`

---

### Task 1.6: Интегрировать ConfidenceBadge в DetailedReport

- [ ] Отображать `ConfidenceBadge` рядом с каждым финансовым показателем
- [ ] Добавить сводную строку: «Извлечено надёжно: N из 15 показателей»
- [ ] Добавить hint: «Показатели с низкой уверенностью (🔴) могут быть исключены из расчёта коэффициентов»

**Затронутые файлы:** `frontend/src/pages/DetailedReport.tsx`

---

## Requirement 2: Многопериодный анализ

### Task 2.1: Создать миграцию Alembic для `multi_analysis_sessions`

- [ ] Создать `migrations/versions/0003_add_multi_analysis_sessions.py`
- [ ] Таблица: `id`, `session_id VARCHAR(64) UNIQUE`, `user_id`, `status`, `progress JSONB`, `result JSONB`, `created_at`, `updated_at`
- [ ] Индексы: `idx_multi_sessions_session_id`, `idx_multi_sessions_created_at`

**Затронутые файлы:** `migrations/versions/0003_add_multi_analysis_sessions.py`

---

### Task 2.2: Добавить модель SQLAlchemy и CRUD-функции

- [ ] Добавить `MultiAnalysisSession` в `src/db/models.py`
- [ ] Добавить в `src/db/crud.py`: `create_multi_session()`, `update_multi_session()`, `get_multi_session()`

**Затронутые файлы:** `src/db/models.py`, `src/db/crud.py`

---

### Task 2.3: Добавить Pydantic-схемы для Multi-Period Analysis

- [ ] `PeriodInput`: `period_label: str = Field(max_length=20)`
- [ ] `PeriodResult`: `period_label`, `ratios`, `score`, `risk_level`, `extraction_metadata`
- [ ] `MultiAnalysisRequest`: `periods: list[PeriodInput] = Field(min_length=1, max_length=5)`
- [ ] `MultiAnalysisProcessingResponse`, `MultiAnalysisCompletedResponse`

**Затронутые файлы:** `src/models/schemas.py`

---

### Task 2.4: Реализовать `process_multi_analysis()` в `tasks.py`

- [ ] Обрабатывает каждый PDF через существующий pipeline последовательно
- [ ] Обновляет `progress: {completed: N, total: M}` после каждого периода
- [ ] Реализовать `parse_period_label(label) -> tuple[int, int]` и `sort_periods_chronologically()`
- [ ] Timeout guard: если обработка > 10 минут → статус `"failed"`
- [ ] Если один PDF не обработан → `{"error": "processing_failed"}` для периода, остальные сохраняются

**Затронутые файлы:** `src/tasks.py`

---

### Task 2.5: Создать роутер `routers/multi_analysis.py`

- [ ] `POST /multi-analysis` → создаёт сессию, запускает BackgroundTask, возвращает 202
- [ ] `GET /multi-analysis/{session_id}` → статус/прогресс или результаты; 404 если не найдено
- [ ] Подключить роутер в `src/app.py`

**Затронутые файлы:** `src/routers/multi_analysis.py`, `src/app.py`

---

### Task 2.6: Реализовать компонент `TrendChart.tsx`

- [ ] Создать `frontend/src/components/TrendChart.tsx`
- [ ] `LineChart` из `@mantine/charts`; `connectNulls: false` для разрывов при `null`
- [ ] Props: `periods: PeriodResult[]`, `selectedRatios: string[]`, `onRatioSelect`, `anomalyThreshold?: number`, `showTrendIndicators?: boolean`
- [ ] Checkbox-список для выбора отображаемых коэффициентов
- [ ] Стрелки ↑↓ на последней точке при `showTrendIndicators: true`
- [ ] Highlight аномальных точек при `anomalyThreshold` задан

**Затронутые файлы:** `frontend/src/components/TrendChart.tsx`

---

### Task 2.7: Интегрировать TrendChart в DetailedReport

- [ ] Добавить вкладку «Динамика» в `DetailedReport.tsx`
- [ ] Обновить `interfaces.ts`: добавить `MultiAnalysisResponse`, `PeriodResult`
- [ ] Polling `GET /multi-analysis/{session_id}` до статуса `"completed"`

**Затронутые файлы:** `frontend/src/pages/DetailedReport.tsx`, `frontend/src/api/interfaces.ts`

---

## Requirement 3: Документация

### Task 3.1: Создать `README.md`

- [ ] Разделы: описание, требования к окружению, установка (≤5 шагов), запуск (dev + production), возможности
- [ ] Упомянуть гибридную архитектуру, offline-ready через Ollama, confidence scoring
- [ ] Команда production-запуска одной строкой

**Затронутые файлы:** `README.md`

---

### Task 3.2: Создать `docs/CONFIGURATION.md`

- [ ] Все переменные окружения: имя, тип, дефолт, описание, обязательность
- [ ] Включить `CONFIDENCE_THRESHOLD`, все AI-провайдеры (`GIGACHAT_*`, `QWEN_*`, `OLLAMA_*`)

**Затронутые файлы:** `docs/CONFIGURATION.md`

---

### Task 3.3: Создать `docs/ARCHITECTURE.md`

- [ ] Layered-архитектура с диаграммой (ASCII или Mermaid)
- [ ] Data flow от загрузки PDF до отображения результата
- [ ] Описание каждого модуля в `src/analysis/` и `src/core/`
- [ ] Раздел про гибридную систему: детерминированный уровень 1 + вероятностный уровень 2

**Затронутые файлы:** `docs/ARCHITECTURE.md`

---

### Task 3.4: Создать `docs/API.md`

- [ ] Все эндпоинты: метод, путь, параметры, тело, ответ, коды ошибок, curl-примеры
- [ ] Включить `POST /multi-analysis` и `GET /multi-analysis/{session_id}`

**Затронутые файлы:** `docs/API.md`

---

### Task 3.5: Создать `docs/BUSINESS_MODEL.md`

- [ ] Целевая аудитория, ценностное предложение, монетизация
- [ ] Конкурентные преимущества (offline-ready, confidence scoring, гибридная архитектура)
- [ ] План развития на 12 месяцев

**Затронутые файлы:** `docs/BUSINESS_MODEL.md`

---

## Requirement 4: Production Build

### Task 4.1: Создать `Dockerfile.backend` (multi-stage)

- [ ] Stage `build`: установка зависимостей
- [ ] Stage `runtime`: минимальный образ без dev-зависимостей

**Затронутые файлы:** `Dockerfile.backend`

---

### Task 4.2: Создать `frontend/Dockerfile.frontend` (multi-stage)

- [ ] Stage `build`: Node.js + `npm ci` + `npm run build`
- [ ] Stage `serve`: Nginx + статика из `dist/`

**Затронутые файлы:** `frontend/Dockerfile.frontend`

---

### Task 4.3: Создать `frontend/nginx.prod.conf`

- [ ] `proxy_pass /api/` → `http://backend:8000/`
- [ ] `try_files` для SPA-роутинга
- [ ] Кэширование статики: `expires 1y; Cache-Control: public, immutable`
- [ ] gzip для JS/CSS/JSON
- [ ] SSL-блок через `envsubst` (включается если `SSL_CERT_PATH` задан)

**Затронутые файлы:** `frontend/nginx.prod.conf`

---

### Task 4.4: Создать `docker-compose.prod.yml`

- [ ] Сервисы: `db`, `backend`, `frontend`
- [ ] Health check `db`: `pg_isready`, interval 10s
- [ ] Health check `backend`: `GET /health`, interval 30s, timeout 10s
- [ ] `backend` depends_on `db: condition: service_healthy`
- [ ] Порты: `80:80`, `443:443` на frontend

**Затронутые файлы:** `docker-compose.prod.yml`

---

### Task 4.5: Создать `scripts/start-prod.sh`

- [ ] Проверка наличия `.env` → выход с ошибкой если отсутствует
- [ ] `docker-compose -f docker-compose.prod.yml up -d --build`
- [ ] Применение миграций Alembic после старта backend

**Затронутые файлы:** `scripts/start-prod.sh`

---

## Requirement 5: Тестовое покрытие

### Task 5.1: Тесты confidence score (pytest)

- [ ] Создать `tests/test_confidence_score.py`
- [ ] Unit-тесты: все 4 уровня уверенности (0.9, 0.7, 0.5, 0.3)
- [ ] Тест дефолтного порога 0.5
- [ ] Тест fallback при неизвестном source → `"derived"`, 0.3

**Затронутые файлы:** `tests/test_confidence_score.py`

---

### Task 5.2: Property-тесты confidence (hypothesis)

- [ ] Создать `tests/test_confidence_properties.py`
- [ ] Property 1: `confidence ∈ [0.0, 1.0]` для всех source
- [ ] Property 2: source→confidence маппинг точный
- [ ] Property 3: фильтрация по threshold корректна для всех входных данных
- [ ] Property 4: подсчёт надёжных показателей совпадает с фильтром
- [ ] Property 7: `confidence ∈ [0.0, 1.0]` для всех валидных PDF-метрик

**Затронутые файлы:** `tests/test_confidence_properties.py`

---

### Task 5.3: Тесты multi-analysis роутера (pytest + hypothesis)

- [ ] Создать `tests/test_multi_analysis_router.py`
- [ ] `POST /multi-analysis` → 202 + session_id
- [ ] `GET /multi-analysis/{session_id}` processing → progress
- [ ] `GET /multi-analysis/{session_id}` not found → 404
- [ ] `POST /multi-analysis` с 6 периодами → 422
- [ ] `POST /multi-analysis` с period_label > 20 символов → 422
- [ ] Property 6: валидация длины period_label
- [ ] Property 7: ограничение 1–5 периодов
- [ ] Property 8: хронологическая сортировка
- [ ] Property 9: round-trip сохранения

**Затронутые файлы:** `tests/test_multi_analysis_router.py`

---

### Task 5.4: Frontend-тесты (vitest)

- [ ] Создать `frontend/src/components/__tests__/TrendChart.test.tsx`
  - [ ] Рендер без ошибок при `null`-значениях в ratios
- [ ] Создать `frontend/src/components/__tests__/ConfidenceBadge.test.tsx`
  - [ ] Зелёный badge при confidence > 0.8
  - [ ] Жёлтый badge при confidence 0.5–0.8
  - [ ] Красный badge при confidence < 0.5
  - [ ] Tooltip содержит «Источник», «Метод», «Уверенность»

**Затронутые файлы:** `frontend/src/components/__tests__/TrendChart.test.tsx`, `frontend/src/components/__tests__/ConfidenceBadge.test.tsx`
