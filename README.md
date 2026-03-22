# ИИ-ассистент финансового директора

Проект для конкурса «Молодой финансист – 2026». Цель — создать MVP ассистента, который автоматически анализирует финансовую отчётность (PDF), считает ключевые финансовые коэффициенты, строит интегральный скоринг и формирует текстовые рекомендации, а также использует локальную LLM для анализа пояснительных записок.

## Структура репозитория

См. подробное описание в `REPO_STRUCTURE.md`. Кратко:

- `backend/` — FastAPI-приложение и модули анализа.
- `frontend/` — статический HTML/CSS/JS фронтенд.
- `data/` — примеры PDF и описание данных.
- `docs/` — планы, спецификации, аналитика.
- `infra/` — Docker и прочая инфраструктура.

## Быстрый старт (разработка)

1. Установите Python 3.10+ и Tesseract OCR.
2. Перейдите в папку `backend/` и установите зависимости:

   ```bash
   pip install -r requirements.txt
   ```

3. Запустите бэкенд (из `backend/`):

   ```bash
   uvicorn app.main:app --reload
   ```

4. Откройте `frontend/index.html` в браузере (или поднимите любой статический сервер) и протестируйте загрузку PDF.

Подробности по задачам недели 1 см. в `docs/WEEK1_TASKS_DETAILED.md`.


## Docker-compose

1. Создайте файл `.env` (можно на основе `.env.example`).
2. Запустите сервисы:

   ```bash
   docker-compose up --build
   ```

3. Backend будет доступен на `http://localhost:8000`, frontend — `http://localhost`.

> Если нужна локальная LLM (Ollama), запустите с профилем:
> `docker-compose --profile ollama up --build`

## Обзор проекта

NeoFin AI — ассистент финансового директора для анализа PDF-отчётности. Он извлекает текст и таблицы, вычисляет ключевые коэффициенты, рассчитывает интегральный скоринг и выполняет NLP-анализ пояснительных записок с помощью локальной LLM.

## Требования

- Python 3.10+
- PostgreSQL 13+
- Tesseract OCR
- Poppler (для pdf2image)
- Docker (опционально, для контейнерного запуска)

## Запуск локально

1. Создайте файл `.env` на основе `.env.example`.
2. Установите зависимости:

   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. Поднимите PostgreSQL и примените миграции:

   ```bash
   alembic upgrade head
   ```

4. Запустите сервер:

   ```bash
   uvicorn src.app:app --reload
   ```

## Запуск через docker-compose

```bash
docker-compose up --build
```

## Пример использования (curl)

```bash
curl -X POST -F "file=@/path/to/report.pdf" http://localhost:8000/upload
curl http://localhost:8000/result/<task_id>
```

## Тестирование и линтеры

```bash
pytest
```

```bash
pre-commit install
pre-commit run --all-files
```

## Тесты в Docker

1. Поднимите базы данных:

   ```bash
   docker-compose up -d db db_test
   ```

2. Запустите тесты в контейнере backend:

   ```bash
   docker-compose run --rm backend sh -lc "pip install -r requirements-dev.txt && pytest"
   ```
