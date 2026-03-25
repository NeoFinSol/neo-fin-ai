# NeoFin AI

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
- Вычисляет 13 коэффициентов: ликвидность, рентабельность, финансовая устойчивость, деловая активность
- Формирует интегральный скоринг 0–100 с уровнем риска и факторами влияния

### Explainability — объяснимость решений

Каждый извлечённый показатель получает **Confidence Score** — оценку надёжности на основе метода извлечения:

| Метод | Источник | Confidence |
|---|---|:---:|
| Точное совпадение ключевого слова в таблице | `table_exact` | 0.9 |
| Частичное совпадение в таблице | `table_partial` | 0.7 |
| Извлечение через regex из текста | `text_regex` | 0.5 |
| Производный расчёт (обязательства = активы − капитал) | `derived` | 0.3 |

Показатели ниже порога `CONFIDENCE_THRESHOLD` (по умолчанию 0.5) автоматически исключаются из расчёта коэффициентов. В UI каждый показатель маркируется цветом: 🟢 > 0.8 / 🟡 0.5–0.8 / 🔴 < 0.5. Tooltip показывает метод извлечения и уровень уверенности. Сводка: «Извлечено надёжно: N из 15 показателей».

### NLP-анализ и рекомендации

- Выявляет финансовые риски и ключевые факторы через языковые модели
- Генерирует 3–5 рекомендаций с явными ссылками на конкретные метрики
- Поддерживаемые провайдеры: GigaChat, DeepSeek (HuggingFace), Ollama (offline)

### Многопериодный анализ

- Сравнивает до 5 отчётных периодов в одной сессии
- Строит интерактивный TrendChart с выбором коэффициентов
- Индикаторы тренда (↑↓) и маркеры аномалий (⚠)
- Хронологическая сортировка периодов (форматы `YYYY`, `Q{N}/YYYY`)

---

## Гибридная архитектура

Система работает на двух независимых уровнях. Недоступность AI-провайдера не влияет на числовой результат.

**Уровень 1 — детерминированный (всегда активен):**
Извлечение данных → Confidence Score → фильтрация по порогу → расчёт коэффициентов → интегральный скоринг. Воспроизводимо, объяснимо, не зависит от внешних сервисов.

**Уровень 2 — вероятностный (AI-слой, опциональный):**
NLP-анализ рисков и генерация рекомендаций через языковые модели. При сбое или недоступности LLM — числовой анализ сохраняется в полном объёме.

```


=======
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
  PostgreSQL (JSONB) → React / Mantine UI (polling 2000 мс)
```

**Выбор AI-провайдера:** определяется один раз при старте приложения по наличию переменных окружения. Нет runtime-переключения между провайдерами.

```
Старт → GIGACHAT_CLIENT_ID задан?  → GigaChat
         HF_TOKEN задан?            → DeepSeek (HuggingFace)
         LLM_URL задан?             → Ollama (полный offline)
         Ничего не настроено?       → NLP отключён, числовой анализ работает

```

---

## Быстрый старт

**Требования:**
- Docker ≥ 24.0
- Docker Compose ≥ 2.20

```bash
# 1. Клонировать репозиторий
git clone https://github.com/your-org/neofin-ai.git && cd neofin-ai

# 2. Создать файл окружения
cp .env.example .env
# Заполнить DATABASE_URL и API_KEY; опционально — ключи AI-провайдеров

# 3. Собрать и запустить
docker-compose up --build

# 4. Открыть
http://localhost

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

## Требования к окружению

- Docker ≥ 24.0
- Docker Compose ≥ 2.20
- (опционально для dev) Python 3.11+, Node.js 20+

---

## Установка
=======
**Требования:** Docker ≥ 24.0, Docker Compose ≥ 2.20
>>>>>>> 6f3b72c (docs: Update)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/your-org/neofin-ai.git && cd neofin-ai

# 2. Создать файл окружения
cp .env.example .env
# Заполнить DATABASE_URL и API_KEY; опционально — ключи AI-провайдеров

# 3. Собрать и запустить (миграции применяются автоматически)
docker-compose up --build

# 4. Открыть: http://localhost
```

**Production:**

```bash
./scripts/start-prod.sh
# Проверяет .env → собирает docker-compose.prod.yml → применяет миграции
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
  -H "Content-Type: application/json" \
  -d '{"periods": [{"period_label": "2021"}, {"period_label": "2022"}, {"period_label": "2023"}]}'
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
| `API_KEY` | — | Ключ доступа к API (обязательно) |
| `CONFIDENCE_THRESHOLD` | `0.5` | Порог надёжности: показатели ниже исключаются из расчётов |
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

---

## Стек

| Слой | Технологии |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy async, Alembic, Pydantic v2 |
| Frontend | React 18, TypeScript, Mantine UI, Recharts, Vite |
| База данных | PostgreSQL 16, JSONB для результатов анализа |
| AI | GigaChat, DeepSeek (HuggingFace), Ollama (offline) |
| Инфраструктура | Docker, Docker Compose, Nginx, multi-stage builds |
| Тестирование | pytest, Hypothesis, vitest, fast-check |
