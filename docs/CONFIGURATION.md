# Конфигурация НеоФин.Документы

## 1. Назначение документа

Документ описывает фактическую конфигурацию среды выполнения проекта:

- параметры приложения;
- параметры инфраструктурного запуска;
- режимы выполнения задач;
- отличия локального и производственного контуров.

Документ опирается на текущие файлы кода и запуска (`src/models/settings.py`, `src/*`, `.env.example`, `docker-compose.yml`, `docker-compose.prod.yml`, `Dockerfile.backend`).

---

## 2. Общая модель конфигурации

### 2.1 Где задаются настройки

1. Файл `.env` (для локального запуска и для compose-контуров с `env_file`).
2. Переменные окружения контейнера (могут переопределять `.env`).
3. Значения по умолчанию в коде (`AppSettings` и прямые `os.getenv` в отдельных модулях).

### 2.2 Уровни конфигурации

- **Уровень приложения** — параметры, которые читает код FastAPI/анализатора.
- **Уровень инфраструктуры запуска** — параметры compose и контейнеров (PostgreSQL, Redis, worker, миграции).
- **Внешний контур** — обратный прокси и сетевой периметр (например, nginx в production compose).

### 2.3 Как читать документ

- Разделы 3–5: параметры и режимы приложения.
- Разделы 6–7: запуск через Docker Compose.
- Раздел 8: сводная таблица переменных с источником, уровнем и дефолтом.
- Пошаговый запуск в среде **Windows** (Docker Desktop, нативный контур, OCR, режимы задач) вынесен в [`docs/INSTALL_WINDOWS.md`](INSTALL_WINDOWS.md), чтобы не дублировать его здесь.

---

## 3. Параметры приложения

В этом разделе перечислены параметры, которые влияют на поведение самого сервера и обработчика анализа.  
Параметры запуска контейнеров и сетевого периметра вынесены в разделы 6–7.

## 3.1 Ключ доступа и режим разработки

- `API_KEY` — ключ для защищенных HTTP-маршрутов.
- `DEV_MODE` (`false` по умолчанию) — отключает проверку `X-API-Key` в HTTP-маршрутах и ослабляет CORS в `src/app.py`.
- `DEMO_MODE` (по умолчанию `0`) — включает маскирование числовых значений в ответах результатов/истории.

## 3.2 Параметры базы данных

Из `AppSettings`:

- `DATABASE_URL`
- `DB_POOL_SIZE` (по умолчанию `5`)
- `DB_MAX_OVERFLOW` (по умолчанию `10`)
- `DB_POOL_TIMEOUT` (по умолчанию `30`)
- `DB_POOL_RECYCLE` (по умолчанию `3600`)
- `DB_POOL_PRE_PING` (по умолчанию `true`)

Из прямого чтения окружения в `src/db/database.py`:

- `TESTING` (по умолчанию `0`)
- `CI` (по умолчанию `0`)
- `TEST_DATABASE_URL` (используется при `TESTING=1`, если задан)

Практически:

- в обычном режиме используется `DATABASE_URL`;
- при `TESTING=1` и заданном `TEST_DATABASE_URL` приложение использует тестовую базу;
- при `TESTING=1` и отсутствии обеих строк подключения используется встроенный тестовый адрес по умолчанию (только для тестового контура).

## 3.3 Параметры фонового выполнения и очередей

Из `AppSettings`:

- `TASK_RUNTIME` (`background` по умолчанию, поддерживаются `background` и `celery`)
- `TASK_STORAGE_DIR`
- `TASK_QUEUE_BROKER_URL`
- `TASK_QUEUE_RESULT_BACKEND`
- `TASK_EVENTS_REDIS_URL`
- `TASK_QUEUE_NAME` (`neofin` по умолчанию)
- `TASK_QUEUE_EAGER` (`false` по умолчанию)

Связанные параметры обслуживания:

- `CLEANUP_BATCH_LIMIT` (по умолчанию `100`)
- `ANALYSIS_CLEANUP_STALE_HOURS` (по умолчанию `48`)
- `MULTI_SESSION_STALE_HOURS` (по умолчанию `24`)
- `RUNTIME_RECOVERY_BATCH_LIMIT` (по умолчанию `100`)
- `ANALYSIS_RUNTIME_STALE_MINUTES` (по умолчанию `60`)
- `MULTI_SESSION_RUNTIME_STALE_MINUTES` (по умолчанию `90`)

## 3.4 Параметры поставщиков языковой модели

Из `AppSettings`:

- GigaChat:
  - `GIGACHAT_CLIENT_ID`
  - `GIGACHAT_CLIENT_SECRET`
  - `GIGACHAT_AUTH_URL` (по умолчанию задан)
  - `GIGACHAT_CHAT_URL` (по умолчанию задан)
- Hugging Face:
  - `HF_TOKEN`
  - `HF_MODEL` (по умолчанию `Qwen/Qwen3.5-9B-Instruct`)
- Qwen:
  - `QWEN_API_KEY`
  - `QWEN_API_URL`
- Локальная модель:
  - `LLM_URL` (по умолчанию `http://localhost:11434/api/generate`)
  - `LLM_MODEL` (по умолчанию `llama3`)

Дополнительно, вне `AppSettings`:

- `GIGACHAT_SSL_VERIFY` (читается в `src/core/gigachat_agent.py`, по умолчанию `true`)

## 3.5 Прочие параметры приложения

- Ограничение запросов:
  - `RATE_LIMIT` (по умолчанию `100/minute`)
- Логи:
  - `LOG_LEVEL` (по умолчанию `INFO`)
  - `LOG_FORMAT` (по умолчанию `text`)
- Порог достоверности и профиль скоринга:
  - `CONFIDENCE_THRESHOLD` (по умолчанию `0.5`)
  - `SCORING_PROFILE` (по умолчанию `auto`)
- Параметры повторных попыток/таймаутов:
  - `AI_TIMEOUT`, `AI_RETRY_COUNT`, `AI_RETRY_BACKOFF` (из `AppSettings`)
  - `RETRY_COUNT`, `RETRY_BACKOFF`, `RETRY_INITIAL_DELAY` (в `src/utils/retry_utils.py`)
  - `AI_CIRCUIT_BREAKER_THRESHOLD`, `AI_CIRCUIT_BREAKER_TIMEOUT` (в `src/utils/circuit_breaker.py`)
- Параметры LLM-извлечения:
  - `LLM_EXTRACTION_ENABLED`, `LLM_CHUNK_SIZE`, `LLM_MAX_CHUNKS`, `LLM_TOKEN_BUDGET`
- Параметры CORS (читаются в `src/app.py`):
  - `CORS_ALLOW_ORIGINS`, `CORS_ALLOW_METHODS`, `CORS_ALLOW_HEADERS`, `CORS_ALLOW_CREDENTIALS`
- OCR-путь (опционально):
  - `TESSERACT_CMD`

---

## 4. Выбор поставщика языковой модели

Поддерживаются четыре поставщика:

- `gigachat`
- `huggingface`
- `qwen`
- `ollama`

Порядок выбора по умолчанию в `AIService`:

1. `gigachat`
2. `huggingface`
3. `qwen`
4. `ollama`

Доступность определяется так:

- **GigaChat**: заданы `GIGACHAT_CLIENT_ID` и `GIGACHAT_CLIENT_SECRET` (и не выглядят как шаблонные значения).
- **Hugging Face**: задан валидный `HF_TOKEN`.
- **Qwen**: заданы `QWEN_API_KEY` и `QWEN_API_URL`; при этом `QWEN_API_URL` не должен быть шаблонным значением по умолчанию `https://api.qwen.ai/v1`.
- **Ollama**: задан `LLM_URL` (по умолчанию задан).

Если поставщики не настроены, языковой анализ деградирует без остановки числового контура анализа.

---

## 5. Режимы выполнения задач

## 5.1 Встроенный фоновый режим (`TASK_RUNTIME=background`)

- используется `BackgroundTasks` в процессе FastAPI;
- отдельный worker и Redis не требуются.

## 5.2 Режим очереди (`TASK_RUNTIME=celery`)

Требуются:

- запущенный Celery worker;
- Redis как брокер очереди (`TASK_QUEUE_BROKER_URL`);
- (опционально) Redis для событий статуса (`TASK_EVENTS_REDIS_URL`, иначе берется `TASK_QUEUE_BROKER_URL`);
- общий путь хранения временных файлов между API и worker (`TASK_STORAGE_DIR`, в compose это `/shared/task-files`).

В режиме `celery` события статусов транслируются через мост Redis -> WebSocket.

---

## 6. Локальный запуск через Docker Compose

Файл: `docker-compose.yml`.

## 6.1 Основной контур

Поднимаются сервисы:

- `backend`
- `worker`
- `backend-migrate`
- `frontend`
- `db`
- `redis`

Фактические особенности локального compose:

- `backend` и `worker` работают в режиме `TASK_RUNTIME=celery`;
- `backend` публикует порт `8000`, `frontend` — порт `80`;
- `db` публикует порт `5432`, `redis` — `6379`;
- `backend-migrate` применяет миграции через `entrypoint.sh`.

## 6.2 Дополнительные профили

- Профиль `test`: добавляет `db_test` (PostgreSQL на `5433`).
- Профиль `ollama`: добавляет сервис `ollama` (порт `11434`).

---

## 7. Производственный контур

Файл: `docker-compose.prod.yml`.

## 7.1 Что подтверждено этим контуром

- публичный входной сервис: `nginx` (в текущем файле опубликован порт `80`);
- `backend`, `worker`, `db`, `redis`, `backend-migrate` во внутренней сети;
- профиль `ollama` доступен отдельно;
- `backend` и `worker` запускаются в режиме `TASK_RUNTIME=celery`.

## 7.2 Важное разделение уровней

- Параметры SSL/TLS относятся к уровню внешнего прокси и инфраструктуры.
- Параметры `SSL_CERT_PATH`, `SSL_KEY_PATH` **не являются параметрами `AppSettings`** и не используются приложением как конфигурация FastAPI.

Если требуется HTTPS, его нужно настраивать на уровне reverse proxy/инфраструктуры, а не как переменные приложения.

---

## 8. Таблица переменных окружения

Ниже только подтвержденные переменные из кода и эксплуатационных файлов.

Пояснение по колонке «По умолчанию»:

- **код** — значение задано в коде приложения;
- **compose** — значение подставляется только на уровне `docker-compose*.yml`;
- **нет** — дефолт не задан, переменная должна быть передана явно;
- **зависит от режима** — значение определяется условиями запуска (например, `TESTING`, профиль compose).

| Переменная | Назначение | Обязательна | По умолчанию | Где используется |
|---|---|---:|---|---|
| `API_KEY` | Ключ доступа к защищенным HTTP-маршрутам | да (кроме `DEV_MODE=1`) | нет | `AppSettings`, `src/core/auth.py` |
| `DEV_MODE` | Режим разработки: отключает проверку API-ключа для HTTP | нет | `false` | `AppSettings`, `auth`, `app` |
| `DEMO_MODE` | Маскирование числовых значений в результатах/истории | нет | `0` | `src/routers/pdf_tasks.py`, `src/routers/analyses.py` |
| `DATABASE_URL` | Основная строка подключения к БД | да (кроме тестовых режимов) | нет | `AppSettings`, `src/db/database.py` |
| `TEST_DATABASE_URL` | Строка подключения для тестового режима | нет | зависит от режима | `AppSettings`, `src/db/database.py`, compose |
| `TESTING` | Переключение на тестовую логику БД | нет | `0` | `src/db/database.py`, compose |
| `CI` | Флаг CI-режима для валидации БД | нет | `0` | `src/db/database.py` |
| `DB_POOL_SIZE` | Размер пула БД | нет | `5` | `AppSettings`, `src/db/database.py` |
| `DB_MAX_OVERFLOW` | Доп. подключения пула БД | нет | `10` | `AppSettings`, `src/db/database.py` |
| `DB_POOL_TIMEOUT` | Таймаут ожидания соединения БД | нет | `30` | `AppSettings`, `src/db/database.py` |
| `DB_POOL_RECYCLE` | Время переразвертывания соединений БД | нет | `3600` | `AppSettings`, `src/db/database.py` |
| `DB_POOL_PRE_PING` | Проверка соединения перед выдачей из пула | нет | `true` | `AppSettings`, `src/db/database.py` |
| `DB_WAIT_RETRIES` | Число попыток миграций при старте | нет | `30` (entrypoint, может быть переопределено в compose) | `entrypoint.sh`, compose |
| `DB_WAIT_SECONDS` | Пауза между попытками миграций | нет | `2` (entrypoint, может быть переопределено в compose) | `entrypoint.sh`, compose |
| `TASK_RUNTIME` | Режим выполнения задач (`background`/`celery`) | нет | `background` (код), в compose часто задан `celery` | `AppSettings`, `src/core/task_queue.py`, compose |
| `TASK_STORAGE_DIR` | Общий путь временных файлов задач | нет | нет | `AppSettings`, роутеры загрузки, compose |
| `TASK_QUEUE_BROKER_URL` | URL брокера очереди задач | для `celery` | нет | `AppSettings`, `task_queue`, `runtime_events`, compose |
| `TASK_QUEUE_RESULT_BACKEND` | URL backend для Celery | нет | нет | `AppSettings`, `task_queue`, compose |
| `TASK_EVENTS_REDIS_URL` | URL Redis для моста событий WebSocket | нет | нет | `AppSettings`, `runtime_events`, compose |
| `TASK_QUEUE_NAME` | Имя очереди Celery | нет | `neofin` | `AppSettings`, `task_queue` |
| `TASK_QUEUE_EAGER` | Выполнение Celery в eager-режиме | нет | `false` | `AppSettings`, `task_queue` |
| `CLEANUP_BATCH_LIMIT` | Пакет очистки зависших записей | нет | `100` | `AppSettings`, скрипты обслуживания |
| `ANALYSIS_CLEANUP_STALE_HOURS` | Порог очистки одиночных задач | нет | `48` | `AppSettings`, скрипты обслуживания |
| `MULTI_SESSION_STALE_HOURS` | Порог очистки многопериодных сессий | нет | `24` | `AppSettings`, скрипты обслуживания |
| `RUNTIME_RECOVERY_BATCH_LIMIT` | Пакет восстановления зависших runtime-записей | нет | `100` | `AppSettings`, скрипты обслуживания |
| `ANALYSIS_RUNTIME_STALE_MINUTES` | Порог runtime-stale для одиночных задач | нет | `60` | `AppSettings`, скрипты обслуживания |
| `MULTI_SESSION_RUNTIME_STALE_MINUTES` | Порог runtime-stale для сессий | нет | `90` | `AppSettings`, скрипты обслуживания |
| `CONFIDENCE_THRESHOLD` | Порог фильтрации достоверности извлечения | нет | `0.5` | `AppSettings`, анализатор |
| `SCORING_PROFILE` | Профиль скоринга (`auto/generic/retail_demo`) | нет | `auto` | `AppSettings`, `scoring` |
| `GIGACHAT_CLIENT_ID` | Идентификатор клиента GigaChat | нет | нет | `AppSettings`, `ai_service` |
| `GIGACHAT_CLIENT_SECRET` | Секрет клиента GigaChat | нет | нет | `AppSettings`, `ai_service` |
| `GIGACHAT_AUTH_URL` | URL OAuth GigaChat | нет | код (`https://ngw.devices.sberbank.ru:9443/api/v2/oauth`) | `AppSettings`, `ai_service` |
| `GIGACHAT_CHAT_URL` | URL чата GigaChat | нет | код (`https://gigachat.devices.sberbank.ru/api/v1/chat/completions`) | `AppSettings`, `ai_service` |
| `GIGACHAT_SSL_VERIFY` | Проверка SSL для клиента GigaChat | нет | `true` | `src/core/gigachat_agent.py`, compose prod |
| `HF_TOKEN` | Токен Hugging Face | нет | нет | `AppSettings`, `ai_service` |
| `HF_MODEL` | Идентификатор модели HF | нет | `Qwen/Qwen3.5-9B-Instruct` | `AppSettings`, `ai_service` |
| `QWEN_API_KEY` | Ключ Qwen API | нет | нет | `AppSettings`, `ai_service`, compose prod |
| `QWEN_API_URL` | URL Qwen API | нет | нет в коде, `https://api.qwen.ai/v1` в compose prod* | `AppSettings`, `ai_service`, compose prod |
| `LLM_URL` | URL локальной языковой модели | нет | код (`http://localhost:11434/api/generate`), в compose может быть переопределен | `AppSettings`, `ai_service`, compose |
| `LLM_MODEL` | Имя локальной модели | нет | код (`llama3`), в compose prod может быть переопределен | `AppSettings`, compose prod |
| `AI_TIMEOUT` | Таймаут вызова языкового сервиса | нет | `120` | `AppSettings`, `ai_service` |
| `AI_RETRY_COUNT` | Повторы вызова языкового сервиса | нет | `2` | `AppSettings`, `ai_service` |
| `AI_RETRY_BACKOFF` | Коэффициент задержки повторов AI | нет | `2.0` | `AppSettings`, `ai_service` |
| `AI_CIRCUIT_BREAKER_THRESHOLD` | Порог срабатывания автомата защиты | нет | `5` | `src/utils/circuit_breaker.py` |
| `AI_CIRCUIT_BREAKER_TIMEOUT` | Время восстановления автомата защиты | нет | `120` | `src/utils/circuit_breaker.py` |
| `RETRY_COUNT` | Число повторов в общих утилитах retry | нет | `3` | `src/utils/retry_utils.py` |
| `RETRY_BACKOFF` | Множитель backoff в общих retry-утилитах | нет | `2.0` | `src/utils/retry_utils.py` |
| `RETRY_INITIAL_DELAY` | Начальная задержка в общих retry-утилитах | нет | `1.0` | `src/utils/retry_utils.py` |
| `RATE_LIMIT` | Ограничение частоты запросов | нет | `100/minute` | `AppSettings`, `app.py` |
| `LOG_LEVEL` | Уровень логирования | нет | `INFO` | `AppSettings`, логирование |
| `LOG_FORMAT` | Формат логирования (`text/json`) | нет | `text` | `AppSettings`, логирование |
| `LLM_EXTRACTION_ENABLED` | Включение LLM-извлечения | нет | `false` | `AppSettings`, `tasks.py` |
| `LLM_CHUNK_SIZE` | Размер текстового блока для LLM-извлечения | нет | `12000` | `AppSettings`, `tasks.py` |
| `LLM_MAX_CHUNKS` | Лимит блоков на документ | нет | `5` | `AppSettings`, `tasks.py` |
| `LLM_TOKEN_BUDGET` | Лимит объема текста на документ | нет | `50000` | `AppSettings`, `tasks.py` |
| `CORS_ALLOW_ORIGINS` | Разрешенные источники CORS | нет | код (список localhost), в `DEV_MODE=1` используется `*` | `src/app.py` |
| `CORS_ALLOW_METHODS` | Разрешенные HTTP-методы CORS | нет | код (`GET,POST,PUT,DELETE,OPTIONS`) | `src/app.py` |
| `CORS_ALLOW_HEADERS` | Разрешенные заголовки CORS | нет | код (базовый список) | `src/app.py` |
| `CORS_ALLOW_CREDENTIALS` | Разрешение credentials для CORS | нет | код (`false`) | `src/app.py` |
| `TESSERACT_CMD` | Явный путь к исполняемому файлу tesseract | нет | нет | `pdf_extractor`, `legacy_helpers` |
| `POSTGRES_USER` | Пользователь PostgreSQL в compose | да для compose | нет (задается в `.env`) | `docker-compose*.yml`, `.env.example` |
| `POSTGRES_PASSWORD` | Пароль PostgreSQL в compose | да для compose | нет (задается в `.env`) | `docker-compose*.yml`, `.env.example` |
| `POSTGRES_DB` | Имя базы PostgreSQL в compose | да для compose | нет (задается в `.env`) | `docker-compose*.yml`, `.env.example` |

\* В `AppSettings` для `QWEN_API_URL` нет дефолта; значение по умолчанию на уровне compose не означает, что дефолт задан в коде приложения.

---

## 9. Типовые сценарии настройки

## 9.1 Минимальный локальный запуск

Минимально:

- заполнить `.env`: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `API_KEY`;
- при необходимости оставить `TASK_RUNTIME` как есть (в локальном compose он переопределяется на `celery`);
- выполнить `docker compose up --build`.

## 9.2 Запуск с очередью задач (Celery/Redis)

Нужно:

- `TASK_RUNTIME=celery`;
- корректный `TASK_QUEUE_BROKER_URL`;
- запущенный worker;
- общий `TASK_STORAGE_DIR` (для многоконтейнерного режима);
- Redis для моста событий (`TASK_EVENTS_REDIS_URL` либо fallback на broker URL).

## 9.3 Запуск с локальным поставщиком языковой модели

Варианты:

- локально вне compose: запустить Ollama и указать `LLM_URL`;
- в compose: использовать профиль `ollama`.

При этом `LLM_MODEL` задает модель по умолчанию, а фактическая доступность зависит от установленной модели в Ollama.

---

## 10. Типовые ошибки конфигурации

- `DATABASE_URL` не задана при обычном запуске -> ошибка инициализации БД.
- `API_KEY` не задан при `DEV_MODE=0` -> защищенные HTTP-маршруты отвечают `500`.
- `TASK_RUNTIME=celery` без `TASK_QUEUE_BROKER_URL` или без Celery/Redis -> ошибки запуска задач (`503` на маршрутах запуска).
- Неверный формат `TASK_QUEUE_*_URL` (не `redis://`/`rediss://`) -> ошибка валидации настроек.
- Неправильный `RATE_LIMIT` или выход параметров `AppSettings` за допустимые диапазоны -> автозамена на безопасные значения с предупреждением в логах.
- Включенный `TESTING=1` в рабочем контуре -> риск подключения к `TEST_DATABASE_URL`.

---

## 11. Примечания по сопровождению

- Обновлять документ при изменении `AppSettings`, прямых `os.getenv` и compose-конфигурации.
- Не добавлять в раздел параметров приложения переменные внешнего прокси/SSL, если они не читаются кодом приложения.
- При изменении порядка выбора поставщиков языковой модели синхронно обновлять раздел 4.
- Для безопасной эксплуатации в контейнерах явно фиксировать `TESTING=0` для `backend`, `worker` и `backend-migrate`.
