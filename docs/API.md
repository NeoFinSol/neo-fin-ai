# API NeoFin AI

## 1. Общая информация

### Базовый адрес

| Среда | URL |
|---|---|
| Локально | `http://localhost:8000` |
| Продакшн | `http://<host>` (порт 80, через Nginx reverse proxy) |

### Формат содержимого

| Операция | Content-Type |
|---|---|
| Загрузка файла | `multipart/form-data` |
| JSON-запрос | `application/json` |
| Все ответы | `application/json` |

### Аутентификация

Все эндпоинты (кроме системных) требуют API-ключ в заголовке:

```
X-API-Key: <ваш-ключ>
```

При `DEV_MODE=1` аутентификация отключена — заголовок не требуется.

| Код | Причина |
|---|---|
| `401` | Заголовок `X-API-Key` отсутствует или содержит неверный ключ |
| `500` | Переменная `API_KEY` не задана на сервере при `DEV_MODE=0` |

### Общие коды ошибок

| Код | Описание |
|---|---|
| `400` | Неверный формат запроса или данных |
| `401` | Ошибка аутентификации |
| `404` | Ресурс не найден |
| `422` | Ошибка валидации тела запроса (Pydantic) |
| `429` | Превышен лимит запросов (rate limiting) |
| `500` | Внутренняя ошибка сервера |
| `503` | Сервис недоступен (база данных не отвечает) |

### Формат ответа при ошибке

```json
{
  "detail": "Описание ошибки"
}
```

---

## 1.1. Оценка достоверности

Каждый извлечённый финансовый показатель сопровождается метаданными о достоверности:

### Источники данных и уровень достоверности

| Источник | Достоверность | Описание |
|----------|------------|----------|
| `table_exact` | 0.9 | Точное совпадение ключевого слова в таблице |
| `table_partial` | 0.7 | Частичное совпадение в строке таблицы |
| `text_regex` | 0.5 | Извлечение через regex из текста |
| `ocr` | 0.5 | Распознано через Tesseract OCR |
| `derived` | 0.3 | Производный расчёт |

### Фильтрация по порогу достоверности

```json
{
  "extraction_metadata": {
    "revenue": {
      "confidence": 0.7,
      "source": "text_regex"
    },
    "net_profit": {
      "confidence": 0.3,
      "source": "derived"
    }
  }
}
```

**Правила:**
- `confidence >= 0.5` (по умолчанию) → показатель используется в расчётах
- `confidence < 0.5` → показатель исключается из расчётов, но виден в UI
- Порог настраивается через `CONFIDENCE_THRESHOLD=0.5`

### Защита от мусорных данных

**Автоматические фильтры:**
- **Годы**: числа 1900–2100 игнорируются
- **Склейки**: числа с >4 пробелами отклоняются
- **Длина**: числа >15 цифр отклоняются
- **Диапазон**: числа <10 000 или >1 трлн отклоняются

---

## 2. Основной анализ

### POST /upload

Загрузка PDF-файла и запуск анализа в фоне. Возвращает `task_id` немедленно, не дожидаясь завершения обработки.

**Запрос**

```
Content-Type: multipart/form-data
X-API-Key: <ключ>
```

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `file` | binary (PDF) | Да | Файл финансовой отчётности. Максимум 50 МБ. |

**Ответ `200 OK`**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Ошибки**

| Код | Причина |
|---|---|
| `400` | Файл не является PDF (проверка magic header `%PDF`) |
| `400` | Файл пустой |
| `400` | Размер файла превышает 50 МБ |
| `500` | Ошибка при сохранении файла или создании записи в БД |

**Пример**

```bash
curl -X POST http://localhost:8000/upload \
  -H "X-API-Key: secret" \
  -F "file=@report_2024.pdf"
```

---

### WebSocket /ws/{task_id}

Уведомления в реальном времени о статусе выполнения задачи. Рекомендуется использовать вместо polling для мгновенного обновления интерфейса.

**URL**: `ws://<host>/ws/{task_id}`

**События (JSON)**:

1.  **Начало извлечения**:
    ```json
    {"status": "extracting", "message": "Извлечение данных из PDF..."}
    ```
2.  **Скоринг**:
    ```json
    {"status": "scoring", "message": "Расчет финансовых коэффициентов..."}
    ```
3.  **AI-анализ**:
    ```json
    {"status": "analyzing", "message": "Генерация выводов через AI..."}
    ```
4.  **Завершение**:
    ```json
    {
      "status": "completed",
      "result": { ... полные данные анализа ... }
    }
    ```
5.  **Ошибка**:
    ```json
    {"status": "failed", "error": "Описание ошибки"}
    ```

**Преимущества**:
- Мгновенное отображение прогресса (progress bar).
- Снижение нагрузки на базу данных (нет частых SELECT запросов).
- Автоматическое закрытие соединения после завершения.

---

### GET /result/{task_id}

Получение статуса и результата анализа. Клиент опрашивает эндпоинт каждые 2000 мс до получения статуса `completed` или `failed`.

**Запрос**

```
X-API-Key: <ключ>
```

| Параметр | Тип | Описание |
|---|---|---|
| `task_id` | string (path) | UUID задачи, полученный от `POST /upload` |

**Ответ `200 OK` — обработка**

```json
{
  "status": "processing"
}
```

**Ответ `200 OK` — завершено**

```json
{
  "status": "completed",
  "filename": "report_2024.pdf",
  "data": {
    "scanned": false,
    "metrics": {
      "revenue": 1000000.0,
      "net_profit": 85000.0,
      "total_assets": 500000.0,
      "equity": 200000.0,
      "liabilities": 300000.0,
      "current_assets": 150000.0,
      "short_term_liabilities": 90000.0,
      "accounts_receivable": 40000.0
    },
    "ratios": {
      "current_ratio": 1.67,
      "quick_ratio": 1.22,
      "absolute_liquidity": 0.31,
      "roa": 0.17,
      "roe": 0.43,
      "ros": 0.085,
      "ebitda_margin": 0.12,
      "equity_ratio": 0.40,
      "leverage": 1.50,
      "interest_coverage": null,
      "asset_turnover": 2.0,
      "inventory_turnover": null,
      "receivables_turnover": 25.0
    },
    "score": {
      "score": 72.5,
      "risk_level": "medium",
      "confidence_score": 0.85,
      "factors": [
        {"name": "Текущая ликвидность", "impact": "positive"},
        {"name": "Рентабельность активов", "impact": "neutral"}
      ],
      "normalized_scores": {
        "current_ratio": 0.87,
        "roa": 0.64
      }
    },
    "nlp": {
      "risks": ["Высокая долговая нагрузка", "Снижение маржи"],
      "key_factors": ["Рост выручки на 12%"],
      "recommendations": ["Сократить краткосрочные обязательства"]
    },
    "extraction_metadata": {
      "revenue": {"confidence": 0.9, "source": "table_exact"},
      "net_profit": {"confidence": 0.5, "source": "text_regex"},
      "liabilities": {"confidence": 0.3, "source": "derived"}
    }
  }
}
```

**Ответ `200 OK` — ошибка обработки**

```json
{
  "status": "failed",
  "error": "PDF processing failed"
}
```

**Поля ответа**

| Поле | Тип | Описание |
|---|---|---|
| `status` | `processing` \| `completed` \| `failed` | Статус задачи |
| `data.scanned` | boolean | `true` — документ распознан через OCR |
| `data.metrics` | object | Извлечённые финансовые показатели (значение `null` — не найдено) |
| `data.ratios` | object | 13 рассчитанных коэффициентов (значение `null` — нехватка данных) |
| `data.score.score` | float \[0–100\] | Интегральный скоринг |
| `data.score.risk_level` | `low` \| `medium` \| `high` \| `critical` | Уровень риска (low ≥ 75, medium 55–74, high 35–54, critical < 35) |
| `data.score.confidence_score` | float \[0.0–1.0\] | Достоверность отчёта (сумма весов найденных данных) |
| `data.score.factors` | array | Факторы с полем `impact`: `positive` \| `neutral` \| `negative` |
| `data.score.normalized_scores` | object | Нормализованные значения \[0.0–1.0\] по каждому коэффициенту |
| `data.nlp` | object | NLP-анализ (пустые массивы если LLM не настроен или произошёл timeout) |
| `data.extraction_metadata` | object | Оценка достоверности и источник для каждого показателя |

**Структура `extraction_metadata`**

| Поле | Тип | Описание |
|---|---|---|
| `confidence` | float \[0.0–1.0\] | Оценка надёжности: 0.9 — `table_exact`, 0.7 — `table_partial`, 0.5 — `text_regex`, 0.3 — `derived`, 0.0 — не найден |
| `source` | string | Метод извлечения: `table_exact`, `table_partial`, `text_regex`, `derived` |

**Ошибки**

| Код | Причина |
|---|---|
| `404` | Задача с указанным `task_id` не найдена |

**Пример**

```bash
curl http://localhost:8000/result/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: secret"
```

---

## 3. История анализов

### GET /analyses

Постраничный список всех анализов, отсортированных по дате создания (новые первые).

**Запрос**

```
X-API-Key: <ключ>
```

| Параметр | Тип | По умолчанию | Описание |
|---|---|---|---|
| `page` | integer ≥ 1 | `1` | Номер страницы |
| `page_size` | integer \[1–100\] | `20` | Количество записей на странице |

**Ответ `200 OK`**

```json
{
  "items": [
    {
      "task_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "completed",
      "created_at": "2024-03-15T10:30:00Z",
      "score": 72.5,
      "risk_level": "medium",
      "filename": "report_2024.pdf"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

**Поля ответа**

| Поле | Тип | Описание |
|---|---|---|
| `items` | array | Список записей анализов |
| `items[].task_id` | string | UUID задачи |
| `items[].status` | string | `processing` \| `completed` \| `failed` |
| `items[].created_at` | datetime (ISO 8601) | Время создания задачи |
| `items[].score` | float \| null | Интегральный скоринг (null если анализ не завершён) |
| `items[].risk_level` | string \| null | Уровень риска (null если анализ не завершён) |
| `items[].filename` | string \| null | Имя загруженного файла |
| `total` | integer | Общее число записей в базе |
| `page` | integer | Текущая страница |
| `page_size` | integer | Размер страницы |

**Примечание:** при `DEMO_MODE=1` числовые значения метрик и коэффициентов маскируются.

**Пример**

```bash
curl "http://localhost:8000/analyses?page=1&page_size=10" \
  -H "X-API-Key: secret"
```

---

### GET /analyses/{task_id}

Полные данные анализа по `task_id`. Endpoint возвращает inner analysis payload из `result.data`, без внешней обёртки `filename`/`data`.

**Запрос**

```
X-API-Key: <ключ>
```

| Параметр | Тип | Описание |
|---|---|---|
| `task_id` | string (path) | UUID задачи |

**Ответ `200 OK`**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "created_at": "2024-03-15T10:30:00Z",
  "data": {
    "scanned": false,
    "metrics": {...},
    "ratios": {...},
    "score": {...},
    "nlp": {...},
    "extraction_metadata": {...}
  }
}
```

**Ошибки**

| Код | Причина |
|---|---|
| `404` | Анализ с указанным `task_id` не найден |

**Пример**

```bash
curl http://localhost:8000/analyses/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: secret"
```

---

## 4. Многопериодный анализ

### POST /multi-analysis

Запуск анализа для нескольких финансовых периодов. Принимает набор PDF-файлов и метки периодов, запускает последовательную обработку в фоне.

**Запрос**

```
Content-Type: multipart/form-data
X-API-Key: <ключ>
```

| Поле | Тип | Ограничения | Описание |
|---|---|---|---|
| `files` | repeated file field | 1–5 элементов | PDF-файлы отчётности, по одному на период |
| `periods` | repeated string field | 1–5 элементов | Метки периодов в том же порядке, что и `files` |

**Правила:**
- количество `files` и `periods` должно совпадать
- метка периода: 1–20 символов, рекомендуемые форматы `YYYY` или `Q{N}/YYYY`

**Ответ `202 Accepted`**

```json
{
  "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "processing"
}
```

**Ошибки**

| Код | Причина |
|---|---|
| `400` | Некорректный формат запроса |
| `422` | Число периодов < 1 или > 5; количество `files` и `periods` не совпадает; `period_label` пустая строка или длиннее 20 символов |

**Пример**

```bash
curl -X POST http://localhost:8000/multi-analysis \
  -H "X-API-Key: secret" \
  -F "files=@report_2022.pdf" \
  -F "files=@report_2023.pdf" \
  -F "periods=2022" \
  -F "periods=2023"
```

---

### GET /multi-analysis/{session_id}

Получение статуса или результатов многопериодного анализа. Клиент опрашивает эндпоинт до получения `status: "completed"`.

**Запрос**

```
X-API-Key: <ключ>
```

| Параметр | Тип | Описание |
|---|---|---|
| `session_id` | string (path) | UUID сессии, полученный от `POST /multi-analysis` |

**Ответ `200 OK` — обработка**

```json
{
  "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "processing",
  "progress": {
    "completed": 1,
    "total": 3
  }
}
```

**Ответ `200 OK` — завершено**

```json
{
  "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "completed",
  "periods": [
    {
      "period_label": "2022",
      "ratios": {
        "current_ratio": 1.45,
        "roa": 0.07,
        "roe": null
      },
      "score": 61.0,
      "risk_level": "medium",
      "confidence_score": 0.55,
      "extraction_metadata": {
        "revenue": {"confidence": 0.9, "source": "table_exact"},
        "equity": {"confidence": 0.3, "source": "derived"}
      }
    },
    {
      "period_label": "2023",
      "ratios": {
        "current_ratio": 1.67,
        "roa": 0.17,
        "roe": 0.43
      },
      "score": 72.5,
      "risk_level": "medium",
      "extraction_metadata": {
        "revenue": {"confidence": 0.9, "source": "table_exact"},
        "equity": {"confidence": 0.7, "source": "table_partial"}
      }
    }
  ]
}
```

**Поля ответа (completed)**

| Поле | Тип | Описание |
|---|---|---|
| `periods` | array | Результаты по каждому периоду, отсортированные хронологически |
| `periods[].period_label` | string | Метка периода |
| `periods[].ratios` | object | Коэффициенты (значение `null` — нехватка данных) |
| `periods[].score` | float \| null | Интегральный скоринг периода |
| `periods[].risk_level` | `low` \| `medium` \| `high` \| `critical` \| null | Уровень риска |
| `periods[].extraction_metadata` | object | Оценка достоверности и источник по каждому показателю |

**Сортировка:** периоды возвращаются в хронологическом порядке независимо от порядка передачи. Форматы меток: `YYYY` сортируется как `(год, 0)`, `Q{N}/YYYY` — как `(год, квартал)`. Нераспознанные метки помещаются в конец.

**Обработка частичных сбоев:** если один из периодов не удалось обработать, он включается в `periods` с полем `{"error": "processing_failed"}`. Остальные периоды сохраняются.

**Ошибки**

| Код | Причина |
|---|---|
| `404` | Сессия с указанным `session_id` не найдена |
| `422` | Обработка сессии завершилась с ошибкой (`status: "failed"`) |

**Пример**

```bash
curl http://localhost:8000/multi-analysis/7c9e6679-7425-40de-944b-e07fc1f90ae7 \
  -H "X-API-Key: secret"
```

---

## 5. Системные эндпоинты

Системные эндпоинты не требуют аутентификации. Используются для health check в Docker Compose и мониторинге.

### GET /system/health

Базовая проверка доступности сервиса. Не проверяет зависимости.

**Ответ `200 OK`**

```json
{
  "status": "ok"
}
```

**Пример**

```bash
curl http://localhost:8000/system/health
```

---

### GET /system/healthz

Расширенная проверка с верификацией зависимостей: подключение к базе данных и статус AI-сервиса.

**Ответ `200 OK` — всё в норме**

```json
{
  "status": "healthy",
  "timestamp": "2024-03-15T10:30:00.000000",
  "components": {
    "database": "healthy",
    "ai_service": "healthy"
  }
}
```

**Ответ `200 OK` — деградация**

```json
{
  "status": "degraded",
  "timestamp": "2024-03-15T10:30:00.000000",
  "components": {
    "database": "unhealthy",
    "ai_service": "not_configured"
  }
}
```

**Поля `components`**

| Компонент | Возможные значения | Описание |
|---|---|---|
| `database` | `healthy` \| `unhealthy` | Результат `SELECT 1` к PostgreSQL |
| `ai_service` | `healthy` \| `not_configured` | Настроен ли хотя бы один LLM-провайдер |

**Примечание:** статус `degraded` возвращается с кодом `200`. Используйте поле `status` для оценки состояния системы. NLP-анализ недоступен при `ai_service: "not_configured"`, числовой анализ продолжает работать.

**Пример**

```bash
curl http://localhost:8000/system/healthz
```

---

### GET /system/ready

Проверка готовности сервиса к приёму трафика. Используется как readiness probe в Docker и Kubernetes.

**Ответ `200 OK`**

```json
{
  "status": "ready"
}
```

**Ответ `503 Service Unavailable`**

```json
{
  "detail": "Service not ready: database connection failed - ..."
}
```

**Пример**

```bash
curl http://localhost:8000/system/ready
```

---

## 6. Справочник

### Финансовые показатели (metrics)

| Ключ | Описание |
|---|---|
| `revenue` | Выручка от реализации |
| `net_profit` | Чистая прибыль |
| `total_assets` | Итого активов |
| `equity` | Собственный капитал |
| `liabilities` | Итого обязательств |
| `current_assets` | Оборотные активы |
| `short_term_liabilities` | Краткосрочные обязательства |
| `accounts_receivable` | Дебиторская задолженность |

Значение `null` означает, что показатель не найден в документе или его уровень достоверности ниже порога `CONFIDENCE_THRESHOLD` (по умолчанию 0.5).

### Финансовые коэффициенты (ratios)

| Ключ | Группа | Описание |
|---|---|---|
| `current_ratio` | Ликвидность | Коэффициент текущей ликвидности |
| `quick_ratio` | Ликвидность | Коэффициент быстрой ликвидности |
| `absolute_liquidity` | Ликвидность | Коэффициент абсолютной ликвидности |
| `roa` | Рентабельность | Рентабельность активов |
| `roe` | Рентабельность | Рентабельность собственного капитала |
| `ros` | Рентабельность | Рентабельность продаж |
| `ebitda_margin` | Рентабельность | Маржа EBITDA |
| `equity_ratio` | Устойчивость | Коэффициент автономии |
| `leverage` | Устойчивость | Финансовый рычаг |
| `interest_coverage` | Устойчивость | Покрытие процентов |
| `asset_turnover` | Активность | Оборачиваемость активов |
| `inventory_turnover` | Активность | Оборачиваемость запасов |
| `receivables_turnover` | Активность | Оборачиваемость дебиторской задолженности |

Значение `null` — коэффициент не рассчитан из-за отсутствия одного или нескольких исходных показателей.

### Источники извлечения

| Значение | Достоверность | Описание |
|---|---|---|
| `table_exact` | 0.9 | Точное совпадение ключевого слова в таблице |
| `table_partial` | 0.7 | Частичное совпадение в таблице |
| `text_regex` | 0.5 | Извлечение через regex из текста |
| `ocr` | 0.5 | Распознано через Tesseract OCR |
| `derived` | 0.3 | Производный расчёт (например, обязательства = активы − капитал) |

При `confidence = 0.0` показатель не найден в документе.

### Форматы period_label

| Формат | Пример | Ключ сортировки |
|---|---|---|
| Год | `2023` | `(2023, 0)` |
| Квартал | `Q1/2023` | `(2023, 1)` |
| Произвольный | `H1-2023` | `(9999, 0)` — в конец списка |

### DEMO_MODE

При переменной окружения `DEMO_MODE=1` числовые значения метрик и коэффициентов в ответах заменяются маскированными строками вида `X,XXX`. Скоринг, уровень риска и факторы сохраняются. Поведение применяется к `GET /result/{task_id}`, `GET /analyses` и `GET /analyses/{task_id}`.
