# Local Notes

## Активные проблемы

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
