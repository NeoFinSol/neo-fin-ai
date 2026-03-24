# Project Log

## 2026-03-24 | Frontend + Backend интеграция: неполная, баги с extraction 🟡
- **Сессия**: Запуск frontend/backend, исправление scoring, попытка исправить PDF extraction
- **Что сделано**:
  - Исправлен `scoring.py`: ключ `"Долговая нагрузка"` → `"Финансовый рычаг"` для совместимости с `ratios.py`
  - Исправлен `DetailedReport.tsx`: приём данных через пропсы вместо `useLocation().state`
  - Исправлен `Dashboard.tsx`: передаёт `result` и `filename` в `DetailedReport`
  - Исправлен `Layout.tsx`: навигация через react-router `Link` вместо `<a href>`
  - Добавлен `HistoryProvider` (context) для хранения истории анализов в localStorage
  - Переписан `AnalysisHistory.tsx`: чтение из контекста вместо mockHistory
  - Добавлены гибкие regex-паттерны в `analyze.py` для pipe-разделителя `"Выручка | 312 567 000"`
  - Обновлены keywords в `pdf_extractor.py` для лучшего matching
  - Добавлена функция `_extract_json_from_response()` для парсинга JSON из markdown-ответов AI
- **Активные баги**:
  - PDF extraction не работает для реальных отчётов Магнит — возвращает только revenue
  - Frontend показывает Score: 0 и только Revenue
  - AI service возвращает текст вместо JSON (markdown с JSON внутри)
- **Файлы**: `src/analysis/scoring.py`, `src/controllers/analyze.py`, `src/analysis/pdf_extractor.py`, `frontend/src/pages/DetailedReport.tsx`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/AnalysisHistory.tsx`, `frontend/src/components/Layout.tsx`, `frontend/src/context/AnalysisHistoryContext.tsx`, `frontend/src/App.tsx`
- **Тесты**: TypeScript lint проходит, но реальная функциональность не проверена
- **Дальше**: Диагностировать почему extraction не работает для реальных PDF; проверить AI service response format
- **Коммит**: pending

---

## 2026-03-24 | Документация проекта: architecture.md, overview.md, local_notes.md, PROJECT_LOG.md ✅
- Созданы четыре управляющих документа для AI-агента: архитектура, обзор состояния, журнал инцидентов, лог изменений
- `architecture.md` — полное описание слоёв, data flow, паттернов, критичных файлов и техдолга
- `overview.md` — живой статус проекта (что работает / в разработке / дальше); `local_notes.md` — архив 13 решённых багов
- **Файлы**: `architecture.md`, `overview.md`, `local_notes.md`, `PROJECT_LOG.md`
- **Тесты**: не писались (документация)
- **Проблемы**: нет
- **Дальше**: начать закрывать CRITICAL-баги из `local_notes.md` — создать `Layout.tsx` и `ProtectedRoute.tsx`

---

## 2026-03-23 | Sprint 0: Безопасность + Qodo code review fixes ✅
- Удалены hardcoded credentials из `database.py`; SSL verification включён для GigaChat; добавлена API Key аутентификация (`src/core/auth.py`) с явным `DEV_MODE=1`
- Qodo review: исправлен риск рекурсии в `invoke_with_retry` (новый `_invoke_once`); lazy validation `DATABASE_URL` перенесена в `get_engine()`; убраны дефолтные пароли из `docker-compose.yml`; добавлен `GIGACHAT_SSL_VERIFY` env
- Добавлен `docker-compose.override.yml.example` для локальной разработки; `tests/conftest.py` автоматически устанавливает `TESTING=1` и `DEV_MODE=1`
- **Файлы**: `src/core/auth.py`, `src/core/ai_service.py`, `src/core/gigachat_agent.py`, `src/db/database.py`, `docker-compose.yml`, `.env.example`, `tests/conftest.py`
- **Тесты**: 264 passed, 1 skipped, 1 error (integration, требует PostgreSQL)
- **Проблемы**: нет
- **Дальше**: Sprint 1 — стабильность (lazy init БД, retry logic, удаление мёртвого кода NLP)

---

## 2026-03-23 | Sprint 1: Стабильность backend ✅
- Lazy initialization engine в `database.py`: `get_engine()` создаёт `AsyncEngine` только при первом вызове; добавлены `get_session_maker()`, `dispose_engine()`; `crud.py` — обработка `IntegrityError` с rollback
- Retry logic в `agent.py`: 3 попытки с exponential backoff (1s, 2s, 4s); разделены типы ошибок (timeout / client / other); добавлен `Content-Type: application/json`
- Удалён мёртвый NLP-код из `tasks.py` (закомментированный импорт и вызов `analyze_narrative`); добавлены docstrings
- Добавлено 11 интеграционных тестов для `/analyze/pdf/file` и `/analyze/pdf/base64` (happy path + error cases + валидация)
- **Файлы**: `src/db/database.py`, `src/db/crud.py`, `src/core/agent.py`, `src/tasks.py`, `tests/test_api.py`
- **Тесты**: покрытие ~60% → ~80%; все новые тесты зелёные
- **Проблемы**: нет
- **Дальше**: расширение `calculate_ratios` до 12 коэффициентов (требование конкурса)

---

## 2026-03-22 | Расширение calculate_ratios: 5 → 12 коэффициентов ✅
- `ratios.py` расширен с 5 до 12 коэффициентов по 4 группам: ликвидность (3), рентабельность (4), финансовая устойчивость (3), деловая активность (3); добавлены `_subtract()`, `_log_missing_data()`
- `pdf_extractor.py` — добавлены 7 новых ключей в `_METRIC_KEYWORDS`: `inventory`, `cash_and_equivalents`, `ebitda`, `ebit`, `interest_expense`, `cost_of_goods_sold`, `average_inventory`
- Обратная совместимость сохранена: при отсутствии новых полей новые коэффициенты возвращают `None`; все ключи остаются русскоязычными (маппинг в `tasks.py`)
- **Файлы**: `src/analysis/ratios.py`, `src/analysis/pdf_extractor.py`, `tests/test_analysis_ratios_new.py`
- **Тесты**: 18 тестов, 100% pass, время 0.21s
- **Проблемы**: frontend `interfaces.ts` и `RATIO_KEY_MAP` в `tasks.py` нужно обновить под новые ключи — см. `local_notes.md#несовместимость-структуры-данных-backend-frontend`
- **Дальше**: подключить NLP pipeline и реализовать модуль рекомендаций

---

## 2026-03-22 | Исправление 11 багов: критические ошибки backend ✅
- Исправлен бесконечный цикл в `analyze.py`: `range(0, 20, 20)` → `range(0, len(file_content), step)` — теперь обрабатываются все страницы PDF
- Заменён `PdfExtractException` на `HTTPException` во всех роутерах; добавлена валидация пустого base64; `payload.update()` защищён проверкой `isinstance(result, dict)`
- CORS вынесен в env-переменные (`CORS_ALLOW_ORIGINS`, `CORS_ALLOW_CREDENTIALS`); добавлен `X-API-Key` в `allow_headers`; `asyncio.timeout()` добавлен в `agent.py`
- **Файлы**: `src/controllers/analyze.py`, `src/routers/analyze.py`, `src/routers/pdf_tasks.py`, `src/tasks.py`, `src/app.py`, `src/models/settings.py`, `src/core/agent.py`
- **Тесты**: синтаксическая проверка всех файлов — OK; unit-тесты не добавлялись
- **Проблемы**: нет (все 11 багов из `local_notes.md` закрыты)
- **Дальше**: Sprint 0 — аудит безопасности (hardcoded credentials, SSL, auth)

---

## 2026-03-22 | Исправление критических frontend-багов + маппинг данных ✅
- Созданы `Layout.tsx` (AppShell + навигация + logout) и `ProtectedRoute.tsx` (redirect на `/login` при `!isAuthenticated`) — фронтенд перестал падать при компиляции
- Добавлен `RATIO_KEY_MAP` и `_translate_ratios()` в `tasks.py`: RU-ключи из `ratios.py` → EN snake_case для frontend; `_build_score_payload()` преобразует `details: dict` → `factors: [{name, description, impact}]`
- Хардкод API ключей заменён на `import.meta.env.VITE_DEV_API_KEY`; скрипты `run.ps1` / `run.bat` переведены на относительные пути с проверкой существования `env/`
- **Файлы**: `frontend/src/components/Layout.tsx`, `frontend/src/components/ProtectedRoute.tsx`, `src/tasks.py`, `frontend/src/pages/Auth.tsx`, `frontend/src/pages/SettingsPage.tsx`, `run.ps1`, `run.bat`
- **Тесты**: не писались; ручная проверка компиляции frontend
- **Проблемы**: `AnalysisHistory.tsx` по-прежнему использует `mockHistory` — см. `local_notes.md`
- **Дальше**: Sprint 0 — безопасность; расширение ratios до 12 коэффициентов

---

## 2026-03-15 | Инициализация проекта и настройка окружения ✅
- Установлен Python 3.12.10; создано виртуальное окружение `env/`; установлено 100+ production и 40+ dev зависимостей; исправлена версия `pdfplumber` (0.11.9 → 0.12.0) для совместимости с Python 3.10+
- Настроен VS Code (`.vscode/settings.json`, `launch.json`, `extensions.json`); созданы скрипты инициализации `init_project.ps1` / `init_project.py`; удалён `safety~=3.0.0` из `requirements-dev.txt` (конфликт с pydantic)
- Базовая структура проекта: FastAPI app, SQLAlchemy async, Alembic миграции, Docker Compose (backend, frontend, db, db_test, ollama), GitHub Actions CI
- **Файлы**: `requirements.txt`, `requirements-dev.txt`, `docker-compose.yml`, `entrypoint.sh`, `.github/workflows/ci.yml`
- **Тесты**: 8 тестов (auth), все зелёные, 3.21s
- **Проблемы**: Python 3.9 несовместим — требуется 3.11+; см. `local_notes.md#pdfminer-six-не-устанавливался-на-python--310`
- **Дальше**: реализация основного pipeline (pdf_extractor → ratios → scoring → NLP)

---

## 2026-03-?? | feat: Data-driven recommendations (commit f01e45d) ✅
- Реализован `src/analysis/recommendations.py` (420 строк): `generate_recommendations()`, `generate_recommendations_with_fallback()`, `_build_recommendations_prompt()` — каждая рекомендация содержит явные ссылки на числовые метрики
- Интегрировано в `src/tasks.py`: вызов после NLP-анализа, timeout 65s, результат в `nlp_result["recommendations"]`; поддержка GigaChat / Qwen / Ollama; graceful degradation при недоступности AI
- Установлены `@mantine/charts@^8.3.18` и `recharts@^2.14.3` для frontend-графиков
- **Файлы**: `src/analysis/recommendations.py`, `src/tasks.py`, `tests/test_recommendations.py`, `frontend/package.json`
- **Тесты**: 29 тестов, 100% pass, 65.83s (включает реальные AI-вызовы в интеграционных тестах)
- **Проблемы**: нет
- **Дальше**: подключить `nlp_analysis.py` (сейчас закомментирован); реализовать реальный API для `AnalysisHistory`
