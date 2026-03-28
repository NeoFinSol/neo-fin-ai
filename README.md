# НеоФин ИИ (NeoFin AI)

**Гибридная AI-платформа финансового анализа предприятий с объяснимыми решениями**

Проект конкурса **«Молодой финансист 2026»**

---

## Что это

NeoFin AI извлекает финансовые данные из PDF-отчётов (включая сканы), оценивает надёжность каждого числа, рассчитывает 13 коэффициентов по четырём группам, формирует интегральный скоринг 0–100 и генерирует рекомендации через языковые модели.

Это не калькулятор коэффициентов. Это AI-система, которая **объясняет происхождение каждого числа** — от сырого PDF до итоговой оценки.

**Какую проблему решает:** ручной анализ PDF-отчётов занимает часы и не даёт оценки надёжности извлечённых данных. NeoFin AI выполняет полный цикл за секунды — и показывает, откуда взято каждое значение.

---

## Возможности

### Извлечение и анализ данных

- Обрабатывает текстовые PDF, таблицы и сканы (OCR через pytesseract)
- **Real-time Updates**: система мгновенных уведомлений через **WebSocket** (прогресс-бары, смена статусов без перезагрузки)
- **Smart PDF Detection**: интеллектуальный выбор метода (анализ первых 3 страниц на наличие текста и изображений `/Image`)
- **OCR Fallback**: автоматическое переключение на Tesseract при обнаружении сканов или невидимых текстовых слоёв
- **OCR Hardening**: multiline-safe numeric extraction не склеивает соседние строки, а fallback OCR-batch соблюдает `MAX_OCR_PAGES`
- **Regression Corpus**: сложные table layouts (note columns, year columns, RSBU line codes, garbled labels, OCR pseudo-tables) зафиксированы corpus-driven тестами
- **Real-PDF Smoke Pack**: committed real annual-report fixtures с `sha256` provenance страхуют text-layer extraction без утяжеления default CI
- **DB Hardening**: async engine применяет pool timeout/recycle, тестовый runtime предпочитает `TEST_DATABASE_URL`, а persistence-boundary больше не маскирует DB failures под `not found`
- **DB Schema Evolution**: `analyses` хранит typed summary-поля (`filename`, `score`, `risk_level`, `scanned`, `confidence_score`, `completed_at`, `error_message`) рядом с каноническим JSONB snapshot; list/history path читает их с fallback на `result`, а cleanup helpers работают в bounded `dry_run`-friendly режиме
- Вычисляет 13 коэффициентов: ликвидность, рентабельность, финансовая устойчивость, деловая активность
- Формирует интегральный скоринг 0–100 с оценкой достоверности (**Confidence Score**) и факторами влияния

### Explainability — объяснимость решений

Система оценивает надёжность каждого числа и всего отчёта в целом:

| Метод | Источник | Confidence | Описание |
|---|---|:---:|---|
| Точное совпадение в таблице | `table_exact` | 0.9 | Ключевое слово точно совпадает с ячейкой таблицы |
| Частичное совпадение в таблице | `table_partial` | 0.7 | Ключевое слово найдено в строке таблицы |
| Извлечение через regex | `text_regex` | 0.5 | Число найдено рядом с ключевым словом в тексте |
| OCR извлечение | `ocr` | 0.5 | Распознано через Tesseract (возможны ошибки) |
| Производный расчёт | `derived` | 0.3 | Вычислено из других метрик (активы − капитал) |

**Механизмы доверия:**
- **Confidence Score отчёта**: интегральный показатель (0.0–1.0) полноты и надёжности данных в `ScoreData`
- **Фильтрация по порогу**: показатели ниже `CONFIDENCE_THRESHOLD` (0.5) исключаются из расчёта коэффициентов
- **Визуальные алерты**: баннеры о низкой достоверности (< 60%) и цветовая маркировка (🟢🟡🔴)
- **Tooltips**: подробная информация об источнике и методе извлечения при наведении

**Защита от мусора:**
- Фильтр лет: числа 1900–2100 игнорируются (это годы отчётности, не данные)
- Фильтр склеек: числа с >4 пробелами отклоняются (несколько колонок таблицы)
- Фильтр длины: числа >15 цифр отклоняются (парсинг ошибки)
- Выбор максимума: из нескольких кандидатов выбирается наибольшее валидное число

### NLP-анализ и рекомендации

- Выявляет финансовые риски и ключевые факторы через языковые модели
- Генерирует 3–5 рекомендаций с явными ссылками на конкретные метрики
- **Token-aware compaction**: перед LLM удаляются page/year noise, дубли строк и low-signal OCR-фрагменты; narrative и recommendation prompts ужимаются до budget-friendly контекста
- **Ресурсная эффективность**: Singleton-управление сессиями для AI-провайдеров, предотвращение port exhaustion
- Поддерживаемые провайдеры: GigaChat, DeepSeek (HuggingFace), Ollama (offline)

### Persistence и runtime hardening

- `analyses` и `multi_analysis_sessions` защищены status constraints на уровне схемы; для lifecycle multi-session добавлен индекс `(status, updated_at)`
- FastAPI lifespan теперь гарантированно вызывает `dispose_engine()` на shutdown, чтобы не оставлять висящие DB connections
- Router boundary переводит ошибки чтения/записи БД в явный service-level failure вместо тихого `404`
- `analyses` использует гибридную модель хранения: полный результат остаётся в JSONB, а hot fields для history/cleanup dual-write'ятся в typed summary columns
- maintenance helpers в `src/db/crud.py` позволяют находить и удалять stale analyses / multi-analysis sessions ограниченными batch'ами с `dry_run=True`

### Многопериодный анализ

- Сравнивает до 5 отчётных периодов в одной сессии
- Строит интерактивный TrendChart с выбором коэффициентов
- Индикаторы тренда (↑↓) и маркеры аномалий (⚠)
- Хронологическая сортировка периодов (форматы `YYYY`, `Q{N}/YYYY`)

---

## Гибридная архитектура

Система работает на трех независимых уровнях. Недоступность AI-провайдера не влияет на числовой результат.

**Уровень 1 — детерминированный (всегда активен):**
Извлечение данных → Confidence Score → фильтрация по порогу → расчёт коэффициентов → интегральный скоринг. Воспроизводимо, объяснимо, не зависит от внешних сервисов.

**Уровень 2 — вероятностный (AI-слой, опциональный):**
NLP-анализ рисков и генерация рекомендаций через языковые модели. При сбое или недоступности LLM — числовой анализ сохраняется в полном объёме.

**Уровень 3 — коммуникационный (WebSocket):**
Real-time менеджер соединений для мгновенного обновления UI при смене фаз анализа.

```

PDF → Extractor → ExtractionMetadata {value, confidence, source}
                        │
       ┌────────────────┤
       ▼                ▼
  Confidence Filter    Explainability UI (🟢🟡🔴 + tooltip)
       │
       ▼
  Ratios (13 коэффициентов, 4 группы)
       │
       ▼
  Scoring (0–100, risk_level, factors, normalized_scores)
       │
       ▼
  AI Analysis (NLP + рекомендации, при наличии провайдера)
       │
       ▼
  WebSocket Broadcast (Real-time update)
       │
       ▼
  PostgreSQL (JSONB + typed summaries) → React / Mantine UI
```

**Выбор AI-провайдера:** определяется один раз при старте приложения по наличию переменных окружения. Нет runtime-переключения между провайдерами.

```
Старт → GIGACHAT_CLIENT_ID задан?  → GigaChat
         HF_TOKEN задан?            → DeepSeek (HuggingFace)
         LLM_URL задан?             → Ollama (полный offline)
         Ничего не настроено?       → NLP отключён, числовой анализ работает

```

---

## Confidence Score: как это работает

Каждый извлечённый показатель получает оценку на основе метода извлечения:

| Метод | Тип источника | Confidence |
|---|---|:---:|
| Точное совпадение ключевого слова в таблице | `table_exact` | 0.9 |
| Частичное совпадение в таблице | `table_partial` | 0.7 |
| Извлечение через regex из текста | `text_regex` | 0.5 |
| Производный расчёт (например, обязательства = активы − капитал) | `derived` | 0.3 |

Показатели ниже `CONFIDENCE_THRESHOLD` (по умолчанию 0.5) автоматически исключаются из расчёта коэффициентов. В UI каждый показатель маркируется цветом: 🟢 > 0.8 / 🟡 0.5–0.8 / 🔴 < 0.5.

---

## Установка

**Требования:** Docker ≥ 24.0, Docker Compose ≥ 2.20

```bash
# 1. Клонировать репозиторий
git clone https://github.com/your-org/neofin-ai.git && cd neofin-ai

# 2. Создать файл окружения
cp .env.example .env
# Заполнить DATABASE_URL и API_KEY; опционально — ключи AI-провайдеров

# 3. Собрать и запустить (миграции применяются автоматически)
docker compose up --build

# 4. Открыть: http://localhost
```

**Production:**

```bash
./scripts/deploy-prod.sh
# Проверяет .env → валидирует docker-compose.prod.yml → собирает образы
# → применяет миграции → поднимает production stack
# Доступно на порту 80
```

---

## Пример использования

**Анализ одного отчёта:**

```bash
# Загрузить PDF
curl -X POST http://localhost/api/upload \
  -H "X-API-Key: your_key" \
  -F "file=@report_2023.pdf"
# → {"task_id": "abc-123"}

# Получить результат (polling до status=completed)
curl http://localhost/api/result/abc-123 \
  -H "X-API-Key: your_key"
# → {"status": "completed", "data": {"ratios": {...}, "score": {...}, "extraction_metadata": {...}}}
```

**Многопериодный анализ:**

```bash
curl -X POST http://localhost/api/multi-analysis \
  -H "X-API-Key: your_key" \
  -F "files=@report_2021.pdf" \
  -F "files=@report_2022.pdf" \
  -F "files=@report_2023.pdf" \
  -F "periods=2021" \
  -F "periods=2022" \
  -F "periods=2023"
# → {"session_id": "xyz-456", "status": "processing"}

curl http://localhost/api/multi-analysis/xyz-456 \
  -H "X-API-Key: your_key"
# → {"status": "completed", "periods": [...]}
```

---

## Тестирование

### Статистика

| Компонент | Тесты | Покрытие | Статус |
|-----------|-------|----------|--------|
| **Backend** | 578 passed | 85% | ✅ |
| **Frontend** | 78 passed | 55% | ✅ |

### Стратегия тестирования

**Unit и integration тесты (570+ тестов):**
- Все unit и integration тесты бизнес-логики проходят успешно
- Покрытие критической бизнес-логики: 85%+
- Property-based тесты (Hypothesis) для проверки инвариантов
- Mock внешних зависимостей (БД, AI-сервис)
- **Regex fallback тесты**: извлечение метрик из текста при отсутствии таблиц
- **LLM budget tests**: compaction, chunk-size invariants, narrative gating и compact JSON recommendation context
- **PDF regression corpus**: note/year columns, multi-period rows, garbled labels и OCR pseudo-table scenarios
- **Real-PDF smoke fixtures**: manifest-driven small corpus с committed PDF-файлами и narrow business assertions

**E2E тесты (9 тестов):**
- Требуют внешних зависимостей (PostgreSQL, AI-сервис)
- Вынесены в отдельный слой тестирования
- Запускаются отдельно с реальной БД через `pytest tests/test_e2e.py -m e2e`

**Frontend тесты:**
- Pure функции: 100% покрытие (buildChartData, getBarColor, THRESHOLDS)
- Components: ConfidenceBadge (100%), TrendChart (95%)
- Hooks: useAnalysisHistory (100%), apiClient (100%)
- Pages: Auth (100%), AnalysisHistory (72%)

---

## Production Docker

### Оптимизация образа

**Multi-stage build:**
- **Builder stage:** компиляция зависимостей (gcc, build-essential, libpq-dev)
- **Runtime stage:** только готовый venv и код приложения
- **Размер:** ~500-600MB vs ~1.2GB (single-stage)

**Безопасность:**
- Non-root пользователь `appuser`
- Read-only code copies с `--chown=appuser:appuser`
- Удалены build-инструменты после компиляции

**Зависимости:**
- **Build stage:** build-essential, libpq-dev, tesseract-ocr, poppler-utils, libgl1
- **Runtime stage:** tesseract-ocr, poppler-utils, libgl1, curl, ca-certificates
- **Исключено:** build-essential, libpq-dev (400-600MB экономии)

**Примечание:** Основной вклад в размер дают OCR и PDF-зависимости (tesseract-ocr, poppler-utils, libgl1) — необходимы для обработки сканов PDF.

### Сборка и запуск

```bash
# Сборка образа
docker build -f Dockerfile.prod -t neofinai:prod .

# Проверка размера
docker images neofinai:prod

# Запуск
docker run -p 8000:8000 --env-file .env neofinai:prod

# Или через docker-compose
docker-compose -f docker-compose.prod.yml up -d --build
```

### Детализация покрытия

**Backend:**
- routers/system.py: 98.65%
- routers/analyses.py: 100%
- core/auth.py: 100%
- analysis/scoring.py: 97.62%
- analysis/ratios.py: 95.59%

**Frontend:**
- api/client.ts: 100%
- hooks/useAnalysisHistory.ts: 100%
- components/ConfidenceBadge.tsx: 100%
- components/TrendChart.tsx: 95%
- pages/Auth.tsx: 100%

---

## Ключевые переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DATABASE_URL` | — | PostgreSQL connection string (обязательно) |
| `TEST_DATABASE_URL` | — | Отдельная БД для тестов; при `TESTING=1` имеет приоритет над `DATABASE_URL` |
| `API_KEY` | — | Ключ доступа к API (обязательно) |
| `CONFIDENCE_THRESHOLD` | `0.5` | Порог надёжности: показатели ниже исключаются из расчётов |
| `DB_POOL_TIMEOUT` | `30` | Сколько ждать свободное DB connection из пула |
| `DB_POOL_RECYCLE` | `3600` | Через сколько секунд пересоздавать stale connections |
| `GIGACHAT_CLIENT_ID` | — | Client ID для GigaChat |
| `GIGACHAT_CLIENT_SECRET` | — | Client Secret для GigaChat |
| `HF_TOKEN` | — | HuggingFace API токен (DeepSeek) |
| `LLM_URL` | — | URL локальной модели Ollama |
| `DEMO_MODE` | `0` | Маскировать числовые данные в ответах API |

Полное описание всех переменных (включая AI-провайдеры, SSL, rate limiting) — в [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md).

---

## Документация

| Файл | Содержание |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Layered-архитектура, data flow, AI pipeline, explainability |
| [`docs/API.md`](docs/API.md) | Все эндпоинты, форматы запросов/ответов, curl-примеры |
| [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) | Все переменные окружения с типами и значениями по умолчанию |
| [`AGENTS.md`](AGENTS.md) | Правила работы агента, orchestration policy и update ritual |
| [`.agent/subagents/README.md`](.agent/subagents/README.md) | Human-readable система субагентов, invocation budget, различие `.toml` registry / `.md` role-spec и separation между project-role и runtime carrier |

---

## Стек

| Слой | Технологии |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy async, Alembic, Pydantic v2 |
| Frontend | React 18, TypeScript, Mantine UI, Recharts, Vite |
| База данных | PostgreSQL 16, JSONB для полного результата + typed summary columns для history/cleanup |
| AI | GigaChat, DeepSeek (HuggingFace), Ollama (offline) |
| Инфраструктура | Docker, Docker Compose, Nginx, multi-stage builds |
| Тестирование | pytest, Hypothesis, vitest, fast-check |
