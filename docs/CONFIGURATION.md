# Конфигурация системы NeoFin AI

## Общая информация

Все параметры задаются через переменные окружения.

- **Локально:** файл `.env` в корне репозитория
- **Production:** переменные окружения контейнера или secrets-менеджер

```bash
cp .env.example .env
# Заполнить обязательные переменные: DATABASE_URL, API_KEY
```

Переменные читаются при старте через `src/models/settings.py` (Pydantic Settings).
При невалидном значении — система логирует предупреждение и применяет значение по умолчанию.

---

## Переменные конфигурации

### Core

| Переменная | Тип | По умолчанию | Обязательная | Описание |
|---|---|---|:---:|---|
| `DATABASE_URL` | `string` | — | ✅ | PostgreSQL connection string. Формат: `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `API_KEY` | `string` | — | ✅ | Ключ аутентификации. Передаётся в заголовке `X-API-Key` |
| `CONFIDENCE_THRESHOLD` | `float` | `0.5` | — | Минимальный confidence score для включения показателя в расчёт. Диапазон: `[0.0, 1.0]` |
| `DEV_MODE` | `bool` | `false` | — | Режим разработки: отключает проверку `API_KEY`, разрешает CORS `*` |
| `DEMO_MODE` | `int` | `0` | — | При `1` — маскирует числовые данные в ответах API |

---

### AI-провайдеры

Провайдер выбирается автоматически при старте в порядке приоритета:

```
GigaChat → DeepSeek (HuggingFace) → Ollama → graceful degrade
```

Если ни один провайдер не настроен — NLP-анализ отключается. Числовой анализ (коэффициенты, скоринг) продолжается в полном объёме.

---

#### GigaChat (приоритет 1)

| Переменная | Тип | По умолчанию | Обязательная | Описание |
|---|---|---|:---:|---|
| `GIGACHAT_CLIENT_ID` | `string` | — | — | Client ID из личного кабинета Sber |
| `GIGACHAT_CLIENT_SECRET` | `string` | — | — | Client Secret из личного кабинета Sber |
| `GIGACHAT_AUTH_URL` | `string` | `https://ngw.devices.sberbank.ru:9443/api/v2/oauth` | — | URL получения OAuth2-токена |
| `GIGACHAT_CHAT_URL` | `string` | `https://gigachat.devices.sberbank.ru/api/v1/chat/completions` | — | URL chat completions API |

Условие активации: заданы оба — `GIGACHAT_CLIENT_ID` и `GIGACHAT_CLIENT_SECRET`.
Требует российского аккаунта Sber. Токен кешируется на 55 минут.

---

#### DeepSeek через HuggingFace (приоритет 2)

Бесплатный доступ к модели DeepSeek через HuggingFace Inference API.

| Переменная | Тип | По умолчанию | Обязательная | Описание |
|---|---|---|:---:|---|
| `HF_TOKEN` | `string` | — | — | HuggingFace API token (формат: `hf_...`) |
| `HF_MODEL` | `string` | `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B` | — | Идентификатор модели на HuggingFace Hub |

Условие активации: задан `HF_TOKEN`.

---

#### Ollama — локальная модель (приоритет 3)

| Переменная | Тип | По умолчанию | Обязательная | Описание |
|---|---|---|:---:|---|
| `LLM_URL` | `string` | `http://localhost:11434/api/generate` | — | URL Ollama API |
| `LLM_MODEL` | `string` | `llama3` | — | Имя модели: `deepseek-r1:7b`, `llama3`, `mistral` и др. |

Условие активации: задан `LLM_URL`. Работает полностью offline без внешних зависимостей.

---

### Backend

| Переменная | Тип | По умолчанию | Обязательная | Описание |
|---|---|---|:---:|---|
| `API_HOST` | `string` | `0.0.0.0` | — | Адрес, на котором слушает FastAPI |
| `API_PORT` | `int` | `8000` | — | Порт FastAPI |
| `RATE_LIMIT` | `string` | `100/minute` | — | Лимит запросов. Формат: `<N>/<second\|minute\|hour\|day>` |
| `LOG_LEVEL` | `string` | `INFO` | — | Уровень логирования: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_FORMAT` | `string` | `text` | — | Формат логов: `text` (dev) или `json` (production) |

---

### Production / SSL

| Переменная | Тип | По умолчанию | Обязательная | Описание |
|---|---|---|:---:|---|
| `SSL_CERT_PATH` | `string` | — | — | Абсолютный путь к SSL-сертификату (`.pem`). При наличии Nginx включает HTTPS на порту 443 |
| `SSL_KEY_PATH` | `string` | — | — | Абсолютный путь к приватному ключу SSL (`.pem`) |

Если `SSL_CERT_PATH` не задан — Nginx работает по HTTP на порту 80. Ошибки запуска не возникает.

---

## Поведение системы

### Выбор AI-провайдера

При старте `AIService._configure()` проверяет переменные в порядке приоритета:

```
1. GIGACHAT_CLIENT_ID + GIGACHAT_CLIENT_SECRET заданы и не пустые?
   → Использовать GigaChat

2. HF_TOKEN задан и не пустой?
   → Использовать DeepSeek через HuggingFace Inference API

3. LLM_URL задан?
   → Использовать Ollama (offline)

4. Ни один провайдер не настроен?
   → NLP-анализ отключён (graceful degrade)
      Возвращаются пустые списки: risks=[], recommendations=[]
      Числовой анализ продолжается без изменений
```

**При сбое провайдера во время запроса** (timeout, сетевая ошибка, HTTP 5xx):
- NLP-блок перехватывает исключение
- Возвращает пустые списки без прерывания обработки
- Числовой результат (коэффициенты, скоринг) сохраняется в БД в полном объёме
- Ошибка логируется с уровнем `WARNING`

Автоматического переключения на следующий провайдер при сбое **не происходит** — провайдер выбирается один раз при старте приложения.

---

### Confidence Threshold

`CONFIDENCE_THRESHOLD` определяет, какие извлечённые показатели участвуют в расчёте финансовых коэффициентов.

**Правило фильтрации:** `confidence >= threshold` → показатель включается в расчёт. Иначе — подставляется `None`.

| Confidence | Метод извлечения | Тип источника | При пороге `0.5` |
|:---:|---|---|:---:|
| `0.9` | Точное совпадение ключевого слова в таблице | `table_exact` | ✅ включается |
| `0.7` | Частичное совпадение в таблице | `table_partial` | ✅ включается |
| `0.5` | Извлечение через regex из текста | `text_regex` | ✅ включается |
| `0.3` | Производный расчёт (например, обязательства = активы − капитал) | `derived` | ❌ исключается |

**Важно:**
- Исключённые показатели **не удаляются** из ответа API — они присутствуют в `extraction_metadata` с фактическим confidence score
- В расчёт коэффициентов вместо исключённого значения подставляется `None`
- Коэффициент, зависящий от `None`-показателя, также принимает значение `None`
- При невалидном значении переменной система применяет `0.5` и логирует `WARNING`

**Рекомендуемые значения:**

| Значение | Режим | Описание |
|---|---|---|
| `0.3` | Мягкий | Включать все показатели, кроме явно ненадёжных |
| `0.5` | Стандартный (по умолчанию) | Баланс полноты и надёжности |
| `0.7` | Строгий | Только таблично извлечённые данные |
| `0.9` | Максимальный | Только точные совпадения в таблицах |

---

## Пример .env

```env
# ── Core ──────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://neofin:password@db:5432/neofin
API_KEY=change-me-in-production
CONFIDENCE_THRESHOLD=0.5

# ── GigaChat (приоритет 1) ────────────────────────────────
GIGACHAT_CLIENT_ID=your-client-id
GIGACHAT_CLIENT_SECRET=your-client-secret

# ── DeepSeek / HuggingFace (приоритет 2) ─────────────────
HF_TOKEN=hf_your_token_here
HF_MODEL=deepseek-ai/DeepSeek-R1-Distill-Qwen-7B

# ── Ollama — offline (приоритет 3) ────────────────────────
LLM_URL=http://ollama:11434/api/generate
LLM_MODEL=deepseek-r1:7b

# ── Backend ───────────────────────────────────────────────
API_HOST=0.0.0.0
API_PORT=8000
RATE_LIMIT=100/minute
LOG_LEVEL=INFO
LOG_FORMAT=json

# ── SSL (production) ──────────────────────────────────────
SSL_CERT_PATH=/etc/nginx/certs/cert.pem
SSL_KEY_PATH=/etc/nginx/certs/key.pem
```
