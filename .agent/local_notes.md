# Local Notes

## Активные проблемы

### WindowsApps executables в Codex сессии могут падать с Access denied
**Статус**: 🟡 Известно
**Дата**: 2026-03-28
**Проблема**: Часть бинарников, найденных в `C:\Program Files\WindowsApps\...`, существует и видна через `where.exe`/`Get-Command`, но subprocess запуск из текущей Codex desktop сессии может падать с `[WinError 5] Отказано в доступе`.
**Где проявилось**:
- `codex.exe --version` из experimental Autopilot spike до миграции в `E:\codex-autopilot`
- `rg.exe` из WindowsApps при локальном exploratory search
**Временное решение**:
- для служебного поиска использовать PowerShell cmdlets (`Get-ChildItem`, `Select-String`) вместо проблемного бинарника
- в `CodexCliAdapter` возвращать явную диагностическую ошибку через `availability_error()`, а не считать runtime silently available
- если установлен standalone `npm i -g @openai/codex`, предпочитать его shim из `PATH` (`codex.cmd`) вместо WindowsApps binary
- для `codex exec` версии `0.117.0` не передавать `-a/--ask-for-approval`: этот флаг есть у верхнего `codex`, но subcommand `exec` его не принимает

---

### Celery + Redis Migration
**Статус**: 🔵 Запланировано
**Проблема**: Текущие `BackgroundTasks` выполняются в памяти и теряются при перезагрузке сервера.
**Решение**: Переход на Celery + Redis для обеспечения персистентности задач.

---

### OCR Performance
**Статус**: ✅ Частично решено (MAX_OCR_PAGES = 50)
**Проблема**: Обработка многостраничных PDF занимает значительное время.
**Решение**: Добавлен лимит `MAX_OCR_PAGES = 50` в `extract_text_from_scanned`. Внедрение параллельной обработки страниц и кэширования — в планах.

---

### BOM в `.flake8`
**Статус**: 🟡 Известно
**Дата**: 2026-03-28
**Проблема**: `python -m flake8 --config=.flake8 ...` падает с `MissingSectionHeaderError`.
**Причина**: файл `.flake8` сохранён с UTF-8 BOM, и текущий `flake8` в этой среде читает первую строку как `\ufeff[flake8]`.
**Временное решение**: запускать `flake8` в `--isolated` режиме и явно передавать ключевые параметры CLI, например `--max-line-length=100`.

---

### `docker compose config` раскрывает секреты из локального `.env`
**Статус**: 🟡 Известно
**Дата**: 2026-03-28
**Проблема**: команда рендерит итоговый compose c уже подставленными env-значениями, поэтому при ручной диагностике/копировании в чат легко утечь чувствительные значения.
**Где проявилось**:
- `docker compose -f docker-compose.yml config`
- `docker compose -f docker-compose.prod.yml config`
**Временное решение**:
- не логировать полный вывод `docker compose config` в issue/чатах
- при проверке compose смотреть только structural sections или локально фильтровать чувствительные поля
- при будущей hardening-итерации рассмотреть `secrets`/`_FILE` pattern для production

---

### Docker daemon может быть недоступен в Codex desktop сессии
**Статус**: 🟡 Известно
**Дата**: 2026-03-28
**Проблема**: `docker compose ... build` может падать не из-за compose-конфига, а потому что недоступен `dockerDesktopLinuxEngine` pipe.
**Где проявилось**:
- `docker compose -f docker-compose.prod.yml build nginx`
**Временное решение**:
- сначала проверять `docker compose ... config`
- отдельно валидировать shell-скрипты (`bash -n scripts/deploy-prod.sh`)
- если нужен реальный build smoke-check, убедиться что Docker Desktop/daemon запущен в хостовой среде

---

## Решённые проблемы

### Сбой shell-команд в sandbox Codex сессии
**Дата**: 2026-03-28
**Проблема**: В этой сессии базовые команды PowerShell в sandbox возвращали `Exit code: 1` без вывода.
**Решение**: Для чтения/редактирования файлов использовать команды вне sandbox (эскалация), после чего работа продолжилась штатно.

### Утечка ресурсов в GigaChat (БАГ 15)
**Дата**: 2026-03-26
**Проблема**: Создание нового `aiohttp.ClientSession` на каждый запрос приводило к port exhaustion.
**Решение**: Внедрён Singleton `_session` в `BaseAIAgent`, который переиспользуется всеми агентами.

### NameError в tasks.py
**Дата**: 2026-03-26
**Проблема**: Обработчик ошибок `_handle_task_failure` пытался обратиться к `file_path`, который не был передан в аргументах.
**Решение**: Рефакторинг `tasks.py`, перенос очистки в `finally` блок родительской функции `process_pdf`.

### Дублирование типов на фронтенде
**Дата**: 2026-03-26
**Проблема**: Файлы `types.ts` и `interfaces.ts` содержали противоречивые определения.
**Решение**: `types.ts` удалён, все импорты переведены на `interfaces.ts`.

---

### 27 failing тестов (e2e/integration)
**Статус**: 🟡 Известно
**Дата**: 2026-03-25
**Проблема**: 27 тестов failing из 577 total (95% passing rate)
**Причина**: Требуют реальную БД и AI-провайдеров.
**Решение**: Разделение тестов на unit (всегда зеленые) и интеграционные (требуют окружения).

---

### Auth fixture не применяется до импорта app
**Статус**: ✅ Решено
**Дата решения**: 2026-03-25
**Решение**: 
- Environment переменные установлены на модульном уровне в conftest.py ДО импорта app
- Добавлен `client` fixture с dependency override для auth
- Все тесты переписаны на использование `client` fixture

```python
# conftest.py — module level
os.environ["TESTING"] = "1"
os.environ["DEV_MODE"] = "1"
os.environ["API_KEY"] = "test-key-for-testing"

@pytest.fixture(scope="function")
def client():
    from fastapi.testclient import TestClient
    from src.app import app
    from src.core.auth import get_api_key
    
    async def override_auth():
        return "test-user"
    
    app.dependency_overrides[get_api_key] = override_auth
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()
```

---

**Связанные задачи**:
- Task 5.3 — Multi-Analysis Router Tests

---

### Rate limiting срабатывает при property-based тестах
**Статус**: 🟡 Известно
**Дата**: 2026-03-25
**Проблема**: Hypothesis генерирует много запросов (50-100 итераций). SlowAPI rate limiter блокирует запросы с ошибкой 429 Too Many Requests.

**Стектрейс/Ошибка**:
```
assert 429 == 202
WARNING slowapi:extension.py:510 ratelimit 100 per 1 minute (testclient) exceeded
```

**Корневая причина**:
- Rate limiter настроен на 100 запросов в минуту
- Hypothesis делает 100+ запросов быстро

**Решение**:
```python
@pytest.fixture(scope="function")
def no_rate_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "1000/second")
    yield
    monkeypatch.undo()
```

**Где применено**: `tests/test_multi_analysis_router.py`

**Связанные задачи**:
- Task 5.3 — Multi-Analysis Router Tests

---

### Score: 0 и пустые факторы во frontend (несовместимость scoring → analyze.py)
**Статус**: Решено ✅
**Дата решения**: 2026-03-24
**Корневая причина**: Два независимых бага:
1. `scoring.py` использовал ключ `"Финансовый рычаг"` в `weights`, а `RATIO_KEY_MAP` в `tasks.py` содержит `"Долговая нагрузка"` — `_build_score_payload()` никогда не находил этот коэффициент в `details`, 10% веса терялось.
2. Fallback-ветка в `analyze.py` (когда AI недоступен) вызывала `score_data.get("factors", [])` и `score_data.get("normalized_scores", {...})` — но `calculate_integral_score()` возвращает `details`, а не `factors`/`normalized_scores`. Frontend получал `score.factors = []` и `score = 0`.

**Решение**:
```python
# src/analysis/scoring.py — исправлен ключ
weights = {
    ...
    "Долговая нагрузка": 0.1,  # было: "Финансовый рычаг"
}

# src/controllers/analyze.py — fallback теперь использует _build_score_payload из tasks.py
from src.tasks import _translate_ratios, _build_score_payload
ratios_en = _translate_ratios(ratios)
score_payload = _build_score_payload(raw_score, ratios_en)
```
Где применено: `src/analysis/scoring.py`, `src/controllers/analyze.py`
Проверка: `POST /analyze/pdf/file` возвращает `score.factors` (непустой список) и `score.score > 0` при наличии метрик в PDF.

---

### [ШАБЛОН] Название проблемы
**Статус**: 🟡 Известно
**Дата**: ГГГГ-ММ-ДД
**Проблема**: Что ломается и при каких условиях.

**Стектрейс/Ошибка**:
```
вставить сюда
```

**Временное решение / Воркэраунд**:
Описание.

**Где смотреть**:
- `src/path/to/file.py` (строка X)

**Связанные задачи**:
- —

---

## Решённые проблемы (архив)

### Утечка ресурсов в GigaChatAgent (ClientSession)
**Статус**: Решено ✅
**Дата решения**: 2026-03-26
**Корневая причина**: Создание новой `aiohttp.ClientSession` на каждый запрос приводило к исчерпанию файловых дескрипторов и портов под нагрузкой.
**Решение**: Внедрена ленивая инициализация сессии (Singleton) с методом `close()`.
**Где смотреть**: `src/core/gigachat_agent.py`

### Низкая достоверность скоринга при неполных данных
**Статус**: Решено ✅
**Дата решения**: 2026-03-26
**Корневая причина**: При отсутствии большинства коэффициентов система могла выдать высокий балл на основе единственного показателя.
**Решение**: Добавлено поле `confidence_score` (сумма весов найденных данных). Фронтенд может предупреждать о низкой полноте отчета.
**Где смотреть**: `src/analysis/scoring.py`

### Ошибки детекции сканированных PDF
**Статус**: Решено ✅
**Дата решения**: 2026-03-26
**Корневая причина**: Проверка только по количеству символов текста давала ложноположительные результаты на PDF с пустыми текстовыми слоями.
**Решение**: Добавлена проверка наличия `/Image` объектов в структуре PDF страниц.
**Где смотреть**: `src/analysis/pdf_extractor.py`

### Dashboard теряет результат анализа при навигации
**Статус**: Решено ✅
**Дата решения**: 2026-03-24
**Корневая причина**: `usePdfAnalysis` хранил состояние локально в хуке. При переходе на другую страницу `Dashboard` размонтировался → хук сбрасывался → `data = null`. Анализ продолжался в фоне, но результат некуда было записать при возврате.

**Решение (чистое)**: создан `AnalysisContext` — отдельный контекст на уровне приложения, который владеет всем состоянием анализа (`status`, `result`, `filename`, `error`, `analyze`, `reset`). `usePdfAnalysis.ts` удалён. `Dashboard` только читает из `useAnalysis()`, не владеет состоянием.

```tsx
// frontend/src/context/AnalysisContext.tsx — новый контекст
export const AnalysisProvider: React.FC<...> = ({ children }) => {
    const [status, setStatus] = useState<AnalysisStatus>('idle');
    const [result, setResult] = useState<AnalysisData | null>(null);
    // ... analyze(), reset()
};

// frontend/src/App.tsx — обёрнут вокруг роутов
<AnalysisProvider>
  <BrowserRouter>...</BrowserRouter>
</AnalysisProvider>

// frontend/src/pages/Dashboard.tsx — только читает
const { status, result, filename, error, analyze, reset } = useAnalysis();
```

Где применено: `frontend/src/context/AnalysisContext.tsx` (новый), `frontend/src/pages/Dashboard.tsx`, `frontend/src/App.tsx`, `frontend/src/context/AnalysisHistoryContext.tsx` (очищен от `pending*`)
Проверка: загрузить PDF → перейти на Settings → вернуться на Dashboard → результат отображается.

> ⚠️ Паттерн: состояние, которое должно пережить навигацию — выносить в отдельный Context на уровне приложения, не хранить в локальном хуке и не примешивать к несвязанным контекстам.

---

### AnalysisHistory — белый экран при клике на запись без данных
**Статус**: Решено ✅
**Дата решения**: 2026-03-24
**Корневая причина**: `handleRowClick` при `res.data.data === null` не устанавливал `detailData`, но и не показывал ошибку. При некоторых условиях `DetailedReport` рендерился с `null` → краш.

**Решение**: явная обработка `null` — показывать `setError(...)` вместо молчаливого игнорирования.

```tsx
if (res.data.data) {
  setDetailData(res.data.data);
} else {
  setError('Данные анализа недоступны — обработка ещё не завершена.');
}
```
Где применено: `frontend/src/pages/AnalysisHistory.tsx`
Проверка: клик на запись без данных → показывает Alert с ошибкой, не белый экран.

---

### load_dotenv не вызывался — DATABASE_URL не читался из .env
**Статус**: Решено ✅
**Дата решения**: 2026-03-24
**Корневая причина**: `database.py` читает `DATABASE_URL` через `os.getenv()` на уровне модуля. `pydantic-settings` загружает `.env` только для `AppSettings`, но не для `os.getenv()`. `load_dotenv()` нигде не вызывался → `DATABASE_URL = None` → `RuntimeError` при старте.

**Решение**:
```python
# src/app.py — добавить в самом начале, до всех импортов src.*
from dotenv import load_dotenv
load_dotenv()
```
Где применено: `src/app.py`
Проверка: backend стартует без `RuntimeError: DATABASE_URL environment variable is required`.

> ⚠️ Паттерн: `os.getenv()` на уровне модуля не читает `.env` автоматически. Всегда вызывать `load_dotenv()` в точке входа приложения.

---

### Auth.tsx — «Не удалось подключиться» даже с валидным ключом
**Статус**: Решено ✅
**Дата решения**: 2026-03-24
**Корневая причина**: Два бага одновременно:
1. `vite.config.ts` proxy указывал на `localhost:5000` (неправильный порт, backend на 8000)
2. `Auth.tsx` и `client.ts` делали запросы напрямую на `http://127.0.0.1:8000` — минуя Vite proxy → браузер блокировал по CORS

**Решение**:
```typescript
// vite.config.ts — исправлен порт
proxy: { '/api': { target: 'http://localhost:8000', ... } }

// Auth.tsx — относительный путь через proxy
await axios.get('/api/analyses?page=1&page_size=1', ...)

// client.ts — baseURL через proxy
baseURL: import.meta.env.VITE_API_BASE || '/api'
```
Где применено: `frontend/vite.config.ts`, `frontend/src/pages/Auth.tsx`, `frontend/src/api/client.ts`
Проверка: `npm run dev` (перезапуск обязателен — proxy конфиг не подхватывается hot reload); запрос в Network tab идёт на `/api/analyses`, не на `127.0.0.1:8000`.

> ⚠️ Паттерн: при ошибке «Не удалось подключиться» в dev — сначала проверить Network tab. Если запрос идёт на `127.0.0.1:8000` напрямую (не через `/api`) — это proxy не используется.

---

### Отсутствуют компоненты Layout и ProtectedRoute
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: Файлы `Layout.tsx` и `ProtectedRoute.tsx` не были созданы, но `App.tsx` их импортировал — фронтенд не компилировался.

**Решение**:
```tsx
// frontend/src/components/ProtectedRoute.tsx
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
};
```
```tsx
// frontend/src/components/Layout.tsx — AppShell с навигацией и logout
// Полный код: docs/old_bugs(corrected)/bugs.txt → Bug 1
```
Где применено: `frontend/src/components/Layout.tsx`, `frontend/src/components/ProtectedRoute.tsx`
Проверка: `npm run build` в `frontend/` без ошибок компиляции.

---

### Несовместимость структуры данных backend ↔ frontend (ratios + score)
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: `ratios.py` возвращал русскоязычные ключи (`"Коэффициент текущей ликвидности"`), `scoring.py` возвращал `details: dict` с числами — frontend ожидал EN snake_case ключи и `factors: [{name, description, impact}]`. `DetailedReport.tsx` крешился на `result.score.factors` (undefined).

**Решение**:
```python
# src/tasks.py — добавлены RATIO_KEY_MAP и функции трансляции
RATIO_KEY_MAP = {
    "Коэффициент текущей ликвидности": "current_ratio",
    "Коэффициент автономии": "equity_ratio",
    "Рентабельность активов (ROA)": "roa",
    "Рентабельность собственного капитала (ROE)": "roe",
    "Долговая нагрузка": "debt_to_revenue",
}

def _translate_ratios(ratios: dict) -> dict:
    return {RATIO_KEY_MAP.get(k, k): v for k, v in ratios.items()}

def _build_score_payload(raw_score: dict, ratios_en: dict) -> dict:
    # Преобразует details: dict → factors: [{name, description, impact}]
    # Полный код: docs/old_bugs(corrected)/bugs.txt → Bug 2
    ...
```
Где применено: `src/tasks.py`
Проверка: `GET /result/{task_id}` возвращает `ratios.current_ratio` (float) и `score.factors` (list).

---

### NLP pipeline не подключён к основному потоку
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: Вызов `analyze_narrative()` был закомментирован в `tasks.py`. `DetailedReport.tsx` показывал заглушки для рисков и рекомендаций.

**Решение**:
```python
# src/tasks.py — добавить после _build_score_payload(), перед update_analysis()
nlp_result = {"risks": [], "key_factors": [], "recommendations": []}
if text and len(text) > 500:
    try:
        from src.analysis.nlp_analysis import analyze_narrative
        nlp_result = await asyncio.wait_for(analyze_narrative(text), timeout=60.0)
    except asyncio.TimeoutError:
        logger.warning("NLP analysis timed out for task %s", task_id)
    except Exception as nlp_exc:
        logger.warning("NLP analysis failed for task %s: %s", task_id, nlp_exc)
# Добавить "nlp": nlp_result в payload update_analysis
```
Где применено: `src/tasks.py`
Проверка: При доступном AI-провайдере `data.nlp.risks` содержит непустой список.

---

### Хардкод API ключей в frontend
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: `Auth.tsx` хардкодил `'neofin_live_test_key_12345'`, `SettingsPage.tsx` — `'neofin_live_550e8400_...'`. Ключи попадали в git.

**Решение**:
```typescript
// frontend/src/pages/Auth.tsx
const apiKey = import.meta.env.VITE_DEV_API_KEY || 'dev_test_key_12345';
login(apiKey);

// frontend/src/pages/SettingsPage.tsx
const apiKey = import.meta.env.VITE_API_KEY || '****-****-****-****';
```
```
# frontend/.env.example
VITE_API_KEY=your_production_api_key_here
VITE_DEV_API_KEY=dev_test_key_12345
```
Где применено: `frontend/src/pages/Auth.tsx`, `frontend/src/pages/SettingsPage.tsx`, `frontend/.env.example`
Проверка: `git grep 'neofin_live'` — пусто.

---

### CORS не пропускал X-API-Key заголовок
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: `allow_headers` в `src/app.py` не включал `X-API-Key` — браузер блокировал preflight-запросы от frontend.

**Решение**:
```python
# src/app.py — в обоих местах (try и except блоки)
# ДО:
["Content-Type", "Authorization", "X-Requested-With"]
# ПОСЛЕ:
["Content-Type", "Authorization", "X-Requested-With", "X-API-Key"]
```
```
# .env.example
CORS_ALLOW_HEADERS=Content-Type,Authorization,X-Requested-With,X-API-Key
```
Где применено: `src/app.py` (строки ~168, ~181), `.env.example`
Проверка: `OPTIONS /upload` возвращает `Access-Control-Allow-Headers: X-API-Key`.

---

### Hardcoded credentials в database.py
**Статус**: Решено ✅
**Дата решения**: 2026-03-23
**Корневая причина**: `DATABASE_URL` имел дефолт `postgresql+asyncpg://postgres:postgres@localhost:5432/neofin` — пароль был известен из кода.

**Решение**:
```python
# src/db/database.py
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is required. "
        "Please set it in your .env file or environment."
    )
```
Где применено: `src/db/database.py`
Проверка: Запуск без `DATABASE_URL` в env падает с `RuntimeError` (fail-fast).

---

### SSL verification отключён для GigaChat
**Статус**: Решено ✅
**Дата решения**: 2026-03-23
**Корневая причина**: `check_hostname = False` + `CERT_NONE` делали соединение уязвимым к MITM. Использовался `__import__('ssl')` вместо нормального импорта.

**Решение**:
```python
# src/core/gigachat_agent.py
import ssl
_gigachat_ssl_context = ssl.create_default_context()
# Убраны: check_hostname = False, verify_mode = CERT_NONE
```
Где применено: `src/core/gigachat_agent.py`
Проверка: Подключение к GigaChat проходит с валидным сертификатом; при невалидном — `ssl.SSLCertVerificationError`.

---

### Нет аутентификации на API endpoints
**Статус**: Решено ✅
**Дата решения**: 2026-03-23
**Корневая причина**: Все endpoints были публичными. Отсутствовала проверка `X-API-Key`.

**Решение**:
```python
# src/core/auth.py (новый файл)
from fastapi.security import APIKeyHeader
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(api_key_header: str = Security(API_KEY_HEADER)) -> str:
    if not API_KEY:  # DEV_MODE: если API_KEY не задан — пропускаем
        return "dev-mode-no-key"
    if api_key_header != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key_header

# Подключено в: src/routers/analyze.py, src/routers/pdf_tasks.py
# @router.post("/upload")
# async def upload_pdf(file: UploadFile, api_key: str = Depends(get_api_key)):
```
Где применено: `src/core/auth.py`, `src/routers/analyze.py`, `src/routers/pdf_tasks.py`
Проверка: `POST /upload` без заголовка → 401. С `X-API-Key: <key>` → 200.

---

### Бесконечный цикл в обработке страниц PDF
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: `for page_idx in range(0, 20, step)` — цикл выполнялся только один раз (range из одного элемента), `return` внутри цикла выходил после первой итерации. Обрабатывались только первые 20 страниц.

**Решение**:
```python
# src/controllers/analyze.py
# ДО:
for page_idx in range(0, 20, step):
    ...
    return json.loads(res)

# ПОСЛЕ:
all_results = []
for page_idx in range(0, len(file_content), step):
    end_idx = min(page_idx + step, len(file_content))
    ...
    all_results.append(json.loads(res))
return all_results[0] if len(all_results) == 1 else {"pages": all_results}
```
Где применено: `src/controllers/analyze.py` (строки 64–65)
Проверка: PDF с >20 страницами обрабатывается полностью.

---

### Кастомное исключение PdfExtractException не обрабатывалось FastAPI
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: `raise PdfExtractException(detail=str(e))` — FastAPI не знает это исключение, приложение падало с 500 без внятного ответа.

**Решение**:
```python
# src/controllers/analyze.py, src/routers/analyze.py
except Exception as e:
    raise HTTPException(status_code=400, detail=f"PDF processing failed: {str(e)}")
```
Где применено: `src/controllers/analyze.py`, `src/routers/analyze.py`
Проверка: Битый PDF → 400 с читаемым `detail`, не 500.

---

### Отсутствие timeout в запросах к AI agent
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: `session.post(url)` без timeout — при недоступном AI сервисе запрос висел бесконечно, блокируя воркер.

**Решение**:
```python
# src/core/agent.py
async def invoke(self, input: dict, timeout: int | None = None) -> str | None:
    actual_timeout = timeout or self.timeout  # default 120s
    try:
        async with asyncio.timeout(actual_timeout):
            return await self.request(...)
    except asyncio.TimeoutError:
        logger.error("Agent request timeout after %d seconds", actual_timeout)
        raise
```
Где применено: `src/core/agent.py`
Проверка: При недоступном Ollama — `TimeoutError` через 120s, не зависание.

---

### Хардкод паролей в docker-compose.yml
**Статус**: Решено ✅
**Дата решения**: 2026-03-23
**Корневая причина**: `POSTGRES_PASSWORD: postgres` захардкожен в `docker-compose.yml` — попадал в git.

**Решение**:
```yaml
# docker-compose.yml
environment:
  POSTGRES_USER: ${POSTGRES_USER:-postgres}
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
  DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/neofin
```
Где применено: `docker-compose.yml`, `.env.example`
Проверка: `docker-compose config` показывает значения из `.env`, не хардкод.

---

### Хардкод путей к Python в run.ps1 / run.bat
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: `E:\neo-fin-ai\venv\Scripts\python.exe` захардкожен — скрипты не работали ни на какой другой машине.

**Решение**:
```powershell
# run.ps1
$pythonPath = ".\env\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
    Write-Host "ERROR: Virtual environment not found. Run: python -m venv env"
    return
}
& $pythonPath -m uvicorn ...
```
Где применено: `run.ps1`, `run.bat`
Проверка: Скрипты запускаются на любой машине с виртуальным окружением в `./env/`.

---

### pdfminer.six не устанавливался на Python < 3.10
**Статус**: Решено ✅
**Дата решения**: 2026-03-15
**Корневая причина**: `pdfplumber~=0.11.9` тянул `pdfminer.six==20251230`, которая требует Python 3.10+. На Python 3.9 установка падала.

**Решение**:
```
# requirements.txt
pdfplumber~=0.12.0   # вместо ~=0.11.9
```
Проект требует Python 3.11+ (зафиксировано в `Dockerfile` и документации).
Где применено: `requirements.txt`
Проверка: `pip install -r requirements.txt` на Python 3.11 без ошибок.

---

### Неправильная валидация result в get_result endpoint
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: `payload.update(analysis.result)` без проверки типа — если `result` не dict (например, строка или None), падал `RuntimeError`.

**Решение**:
```python
# src/routers/pdf_tasks.py (строка ~44)
if analysis.result and isinstance(analysis.result, dict):
    payload.update(analysis.result)
```
Где применено: `src/routers/pdf_tasks.py`
Проверка: `GET /result/{id}` при `result=None` или `result="error string"` → корректный JSON без 500.
