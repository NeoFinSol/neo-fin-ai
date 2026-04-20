# Запуск НеоФин.Документы на Windows

## 1. Назначение документа

Этот документ — **практическое** руководство по локальному запуску проекта в среде **Windows 10/11 x64**. Он не заменяет справочник по переменным окружения: детали параметров, таблица переменных и различие уровней конфигурации описаны в [`docs/CONFIGURATION.md`](CONFIGURATION.md).

Общая картина продукта и ссылка на остальную документацию — в корневом [`README.md`](../README.md); пользовательский веб-клиент — в [`frontend/README.md`](../frontend/README.md).

---

## 2. Какой способ запуска рекомендуется для Windows

**Рекомендуемый путь для большинства случаев — Docker Compose** (Docker Desktop): так поднимаются те же сервисы, что заложены в `docker-compose.yml` (PostgreSQL, Redis, backend, worker обработки задач, фронтенд за nginx), без ручной сборки цепочки OCR на хосте.

**Запуск сервера и интерфейса напрямую на Windows** имеет смысл, если вы разрабатываете бэкенд или фронтенд и готовы отдельно установить PostgreSQL, цепочку **Ghostscript + Tesseract + Poppler** и при необходимости **Redis** и процесс **Celery worker**. Этот путь ближе к «классической» разработке, но требует больше ручных шагов и не повторяет полностью контейнерный контур без дополнительной настройки.

**Упрощённый сценарий** (только Python + Node + своя база, `TASK_RUNTIME=background`) подходит для быстрой отладки логики в одном процессе, но **не эквивалентен** полному контуру с очередью: при `celery` часть поведения (отдельный воркер, мост событий в WebSocket) реализуется иначе.

---

## 3. Предварительные требования

### Общие

- **Git**
- **Windows 10/11 x64**

### Для сценария с Docker Desktop

- **Docker Desktop** (включена интеграция WSL2, если установщик это предлагает)

### Для нативного сценария (без Docker)

- **Python 3.11** (как в `Dockerfile.backend`; удобно через установщик python.org или `py -3.11`)
- **Node.js 20+** (как в `frontend/Dockerfile` для сборки; для `npm run dev` достаточно совместимой LTS)
- **PostgreSQL 16** (или другая доступная вам версия; в compose используется образ `postgres:16-alpine`)

### Для извлечения с OCR на хосте (без Docker-бэкенда)

- **Ghostscript** — в `PATH` должен быть вызываемый `gswin64c` (или эквивалент из установки)
- **Tesseract OCR** с языком **`rus`** — команды `tesseract --version` и `tesseract --list-langs`
- **Poppler** — утилита `pdfinfo` в `PATH`

Официальные страницы загрузок (при обновлении инструкции сверяйте актуальные ссылки):

- Ghostscript: https://ghostscript.com/releases/gsdnld.html  
- Tesseract (Windows): https://github.com/UB-Mannheim/tesseract/wiki  
- Poppler (Windows): https://github.com/oschwartz10612/poppler-windows/releases  

### Переменная `TESSERACT_CMD`

Если исполняемый файл Tesseract не находится автоматически, в окружении можно задать **`TESSERACT_CMD`** полным путём к `tesseract.exe` (см. использование в коде извлечения). Подробности списка переменных — в [`docs/CONFIGURATION.md`](CONFIGURATION.md).

### Локальная языковая модель (необязательно)

- **Ollama для Windows**: https://ollama.com/download/windows  

В типовом **Docker Compose** из репозитория адрес модели по умолчанию указывает на хост: `LLM_URL=http://host.docker.internal:11434/api/generate` — то есть **Ollama ожидается на машине Windows**, а не обязательно в контейнере. Чтобы поднять Ollama в Docker, используется профиль `ollama` (см. раздел 6).

---

## 4. Подготовка окружения

1. Клонировать репозиторий и перейти в каталог проекта (пример):

   ```powershell
   git clone <URL-репозитория>
   cd E:\neo-fin-ai
   ```

2. Создать файл **`.env`** из шаблона:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Заполнить **обязательные** для compose значения из `.env.example`, как минимум:

   - `API_KEY`
   - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`

   Для первого знакомства с проектом на своей машине можно скопировать **`docker-compose.override.yml.example`** в **`docker-compose.override.yml`** (файл не коммитится): в примере заданы простые учётные данные только для **локальной** базы — см. комментарии внутри файла.

4. Режим разработки по HTTP: при **`DEV_MODE=1`** проверка ключа `X-API-Key` для HTTP-маршрутов отключается; для **WebSocket** при включённом `DEV_MODE` проверка ключа также ослабляется в коде сервера (удобно для локальной связки с Vite). В продакшене `DEV_MODE` не используйте. Сводка правил доступа — в [`docs/API.md`](API.md).

---

## 5. Быстрый локальный запуск (Docker Compose)

Из корня репозитория:

```powershell
docker compose up --build
```

Либо в фоне:

```powershell
docker compose up -d --build
```

После успешного старта (см. раздел 8):

- **Веб-интерфейс** (nginx, порт **80**): `http://localhost` или `http://127.0.0.1`  
- Запросы к API с той же машины через прокси фронтенда: префикс **`/api/`** (например, `http://localhost/api/system/health`) — см. `frontend/nginx.prod.conf`  
- **Прямой** доступ к серверу FastAPI на хосте: `http://localhost:8000` (порт проброшен из сервиса `backend`)

Дополнительные профили compose (см. `docker-compose.yml`):

- **`--profile ollama`** — поднять контейнер Ollama вместо использования установки на хосте  
- **`--profile test`** — отдельная тестовая база `db_test` (порт **5433** на хосте)

**Важно про режим задач в compose:** в файле `docker-compose.yml` для сервисов `backend` и `worker` в секции `environment` **явно задано** `TASK_RUNTIME=celery` и URL Redis. Это **перекрывает** значение `TASK_RUNTIME` из `.env` для этих контейнеров. То есть стек по умолчанию — **очередь Celery + Redis + отдельный worker**, а не встроенный `background` внутри одного только процесса uvicorn.

---

## 6. Полный локальный контур

### 6.1 Что входит в «полный» контур под Windows

| Компонент | Docker Compose (рекомендуемый) | Нативно (вручную) |
|-----------|-------------------------------|-------------------|
| API | Сервис `backend` | `uvicorn src.app:app --host 0.0.0.0 --port 8000` в активированном venv |
| База данных | Сервис `db` (PostgreSQL 16) | Локальный PostgreSQL, строка `DATABASE_URL` на `localhost` |
| Очередь задач | `TASK_RUNTIME=celery`, Redis, сервис `worker` | Установить Redis, задать `TASK_RUNTIME=celery` и URL брокера, запустить worker (см. раздел 7) |
| Фронтенд | Сервис `frontend` (nginx, порт 80) | `npm --prefix frontend run dev` (порт **3000**, прокси `/api` на бэкенд в `vite.config.ts`) |
| Миграции БД | Сервис `backend-migrate` через `entrypoint.sh` | Вручную из venv: `alembic upgrade head` при готовой базе |

### 6.2 Нативный backend и venv

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
```

Перед первым запуском убедитесь, что PostgreSQL доступен и в **`.env`** указан корректный **`DATABASE_URL`** для **localhost** (не имя хоста `db` из compose).

Применить миграции:

```powershell
alembic upgrade head
```

Запуск API:

```powershell
uvicorn src.app:app --host 0.0.0.0 --port 8000
```

### 6.3 Нативный frontend

```powershell
npm --prefix frontend install
npm --prefix frontend run dev
```

Интерфейс: `http://localhost:3000` (см. [`frontend/README.md`](../frontend/README.md)). Бэкенд по умолчанию ожидается на `http://localhost:8000` через прокси.

### 6.4 OCR на хосте

Если бэкенд запускается на Windows **без** Docker-образа, в котором уже установлены системные зависимости, цепочку Ghostscript / Tesseract / Poppler нужно установить и проверить командами из раздела 3. Иначе часть PDF (сканы) не сможет пройти OCR.

---

## 7. Режимы выполнения задач

### `background` (в процессе приложения)

- Значение по умолчанию в **`AppSettings`** и в `.env.example` для **приложения**.
- Подходит для **одного процесса** `uvicorn`: задачи ставятся во встроенные фоновые задачи FastAPI, WebSocket и опрос результата работают в рамках этого процесса.
- **Не требует** Redis и отдельного worker.

### `celery` (очередь и отдельный воркер)

- Используется в **`docker-compose.yml`** для сервисов `backend` и `worker`: задачи уходят в Redis, исполняет отдельный контейнер `worker` (команда Celery из образа бэкенда).
- Нужны **`TASK_QUEUE_BROKER_URL`**, **`TASK_QUEUE_RESULT_BACKEND`**, **`TASK_EVENTS_REDIS_URL`** (в compose заданы на сервис `redis`).
- Для **нативного** Windows-запуска с `celery` потребуется: запущенный Redis, тот же `DATABASE_URL` и общий каталог задач при использовании **`TASK_STORAGE_DIR`**, затем второй процесс, например:

  ```powershell
  celery -A src.core.task_queue:celery_app worker --loglevel=INFO -Q neofin
  ```

  (из активированного venv, имя очереди по умолчанию совпадает с `TASK_QUEUE_NAME=neofin` в `.env.example`).

**Когда что выбирать:** для повторения «как в репозитории по умолчанию» на Windows — **Docker Compose с celery**. Для минимальной отладки кода без очереди — локально **`TASK_RUNTIME=background`** и один процесс uvicorn.

---

## 8. Проверка, что система поднялась корректно

### После Docker Compose

- Состояние API: в браузере или через клиент HTTP откройте  
  `http://localhost/api/system/health`  
  либо напрямую  
  `http://localhost:8000/system/health`
- Контейнеры: `docker compose ps` — сервисы `backend`, `frontend`, `db`, `redis`, `worker` в состоянии running / healthy (как определено в compose).

### После нативного запуска

- `http://127.0.0.1:8000/system/health` (или `Invoke-WebRequest` в PowerShell).

### Ollama (если используете)

```powershell
ollama list
```

---

## 9. Типовые проблемы на Windows

- **Порт 80 занят** — остановите конфликтующий сервис или измените проброс портов (это уже правка compose, не описывается здесь как обязательная).
- **Порт 5432 или 6379 занят** — локальный PostgreSQL/Redis на хосте мешает контейнерам; остановите службу или измените проброс в compose.
- **OCR не работает на нативном бэкенде** — проверьте `PATH`, наличие `rus` в Tesseract и при необходимости **`TESSERACT_CMD`**.
- **`host.docker.internal`** — в compose LLM по умолчанию смотрит на Ollama на хосте; если Ollama не запущен, языковой слой может быть недоступен, **детерминированный** расчёт при этом сохраняется (см. архитектуру в [`docs/ARCHITECTURE.md`](ARCHITECTURE.md)).
- **WebSocket** при отключённом `DEV_MODE` и заданном `API_KEY` закрывается с **прикладным кодом 4001**, если ключ в строке запроса отсутствует или неверен (см. [`docs/API.md`](API.md)); для HTTP используется заголовок `X-API-Key`.
- **Миграции** — при нативном запуске не забывайте `alembic upgrade head`; в Docker их выполняет этап `backend-migrate`.

---

## 10. Когда смотреть `docs/CONFIGURATION.md`

Переходите к [`docs/CONFIGURATION.md`](CONFIGURATION.md), если нужно:

- полная таблица переменных и источник значений по умолчанию;
- цепочка поставщиков языковой модели, CORS, лимиты, пулы БД;
- описание **`docker-compose.prod.yml`** как отдельного производственного контура (этот файл **не** является пошаговой инструкцией локального запуска на Windows).

---

## 11. Краткие замечания по сопровождению

- Проект развивается как модуль экосистемы **НеоФин.Контур**; конкурсные runbook’и не задают основной порядок запуска (см. архив в корневом `README.md`).
- Скоуп профиля скоринга задаётся **`SCORING_PROFILE`** (`auto` по умолчанию в `.env.example`); это не заменяет чтение [`docs/CONFIGURATION.md`](CONFIGURATION.md) при смене среды.
- Рекомендуемая локальная модель для тяжёлых JSON-сценариев с Ollama в комментариях `.env.example` указана как **`qwen3.5:9b`**; код по умолчанию для `LLM_MODEL` может отличаться — явно задайте модель в `.env`, если используете Ollama.

## Связанные документы

- [`README.md`](../README.md) — обзор продукта и ссылки на ядро документации  
- [`docs/CONFIGURATION.md`](CONFIGURATION.md) — конфигурация и режимы  
- [`docs/API.md`](API.md) — маршруты и доступ  
- [`frontend/README.md`](../frontend/README.md) — запуск и роль клиента  
