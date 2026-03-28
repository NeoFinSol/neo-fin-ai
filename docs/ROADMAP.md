# NeoFin AI — Roadmap (Планы развития)

**Дата создания**: 2026-03-25  
**Последнее обновление**: 2026-03-28  
**Приоритеты**: HIGH → MEDIUM → LOW

---

## Контекст на сегодня

К моменту этого обновления уже закрыты опорные волны стабилизации:

- `Audit Wave 1-3D`: product-contract fixes, LLM token compaction, PDF regression corpus, real-PDF smoke pack, DB hardening, DB schema evolution, bounded admin cleanup job
- production Docker path выровнен и не зависит от локального `frontend/dist`
- human-readable orchestration усилен: role-binding, hard invocation protocol, deep synthesis ladder

Следующий этап уже не про хаотичный cleanup, а про последовательное добивание accuracy, runtime и ops-hardening.

---

## 🚀 Execution Plan — ближайший горизонт (1-3 недели)

### EP-1 — Cleanup job operationalization [HIGH]
**Цель**: довести `scripts/admin_cleanup.py` до реального эксплуатационного сценария.

**Уже есть**:
- bounded cleanup helpers в `src/db/crud.py`
- orchestration layer в `src/maintenance/cleanup_jobs.py`
- admin CLI с `dry_run` по умолчанию

**Что осталось**:
- [ ] описать production runbook для cron / Windows Task Scheduler
- [ ] зафиксировать retention policy и batch strategy для ops
- [ ] добавить checklist безопасного first-run (`dry_run` → review → `--execute`)
- [ ] определить, нужен ли отдельный ops smoke-report для cleanup job

**Критерий готовности**:
- cleanup job можно безопасно запускать по расписанию без риска удаления completed history

---

### EP-2 — Test hygiene и warning cleanup [HIGH]
**Проблема**: часть тестового контура уже зелёная, но среда шумит и скрывает реальные регрессии.

**Что сделать**:
- [ ] зафиксировать `pytest-asyncio` loop-scope конфиг без warning’ов
- [ ] убрать существующий путь с unclosed `aiohttp` session
- [ ] триажнуть legacy `tests/test_tasks_coverage.py` и решить: обновить или удалить как устаревший compatibility suite
- [ ] сократить шум deprecation warning’ов вокруг `pypdf` / `ARC4`, где это контролируется кодом или зависимостями

**Критерий готовности**:
- fast regression suite остаётся зелёным и шум warning’ов больше не маскирует новые проблемы

---

### EP-3 — Heavy/OCR real-PDF tier [HIGH]
**Цель**: добавить медленный, но честный accuracy-слой поверх уже существующего real-PDF smoke pack.

**Уже есть**:
- committed real-PDF smoke fixtures
- synthetic corpus для сложных layouts
- OCR fallback hardening и anti-regression tests

**Что сделать**:
- [ ] выделить optional pytest-tier для OCR-heavy / table-heavy fixtures
- [ ] подобрать curated набор больших real PDF с многостраничными таблицами
- [ ] определить узкие acceptance assertions: metrics, sources, confidence expectations
- [ ] не смешивать этот tier с default fast CI path

**Критерий готовности**:
- у проекта есть отдельный медленный regression-layer для реальных OCR-heavy отчётов

---

## 📅 Следующий горизонт (3-6 недель)

### EP-4 — Persistent runtime вместо in-process BackgroundTasks [HIGH]
**Проблема**: при рестарте backend текущие задачи теряются, а статус может зависнуть в `processing`.

**Основной safe path**:
- [ ] design pass для persistent job runner
- [ ] выбрать стек: `Celery + Redis` или функционально эквивалентный persistent queue
- [ ] вынести task lifecycle из in-process `BackgroundTasks`
- [ ] сохранить совместимость API/status lifecycle для frontend
- [ ] добавить retry / recovery semantics

**Критерий готовности**:
- рестарт backend больше не ломает длинные PDF/OCR задачи

---

### EP-5 — Production hardening и deploy confidence [HIGH]
**Что уже сделано**:
- production compose hardening
- self-contained frontend image
- nginx security headers и rate limiting

**Что осталось**:
- [ ] deploy smoke на реальной VPS/production-like среде
- [ ] HTTPS / SSL termination path
- [ ] backup / restore runbook
- [ ] health-check / alerting baseline

**Критерий готовности**:
- production deployment воспроизводим и проходит минимальный operational smoke

---

### EP-6 — PDF accuracy wave 2 [MEDIUM]
**Фокус**: качество парсинга после появления heavy-tier regression base.

**Что сделать**:
- [ ] multi-column extraction heuristics для real ambiguous layouts
- [ ] Camelot lattice / fallback strategy для сложных таблиц
- [ ] OCR batching / caching / performance profiling
- [ ] при необходимости расширить API явным period disambiguation

**Критерий готовности**:
- меньше silent-misparse на annual reports со сложной вёрсткой

---

## 🔮 Дальше по roadmap (6+ недель)

### EP-7 — S3/MinIO для временных PDF [MEDIUM]
- [ ] уйти от локального временного хранения файлов
- [ ] подготовить path для multi-instance runtime

### EP-8 — Интерактивные OCR corrections [MEDIUM]
- [ ] дать пользователю возможность поправлять извлечённые значения
- [ ] сохранить explainability между raw extraction и user-adjusted values

### EP-9 — Industry benchmarks / OKVED layer [MEDIUM]
- [ ] добавить отраслевые нормативы и сравнение по секторам
- [ ] расширить scoring explainability отраслевым контекстом

### EP-10 — API-first / white-label surface [LOW]
- [ ] более формализованный публичный API
- [ ] sandbox / partner integration path

---

## ✅ Уже выполнено и больше не является ближайшим блокером

- [x] `critical` risk level и scoring-factor explainability
- [x] contract alignment между backend, frontend и WebSocket lifecycle
- [x] LLM token optimization без смены внешнего API
- [x] OCR fallback hardening и anti-merge numeric guards
- [x] complex-layout synthetic PDF corpus
- [x] real-PDF smoke fixture pack
- [x] DB hardening: pool/runtime/schema guards
- [x] DB schema evolution с typed summary columns
- [x] bounded admin cleanup CLI
- [x] human-readable subagent manifests и hard invocation protocol

---

## 📊 Метрики успеха

| Метрика | Сейчас | Ближайшая цель |
|---------|--------|----------------|
| Fast regression suite | Стабильно зелёная на целевых наборах | Минимум warning noise |
| Real-PDF coverage | Smoke-level fixtures + synthetic corpus | Heavy/OCR optional tier |
| Task runtime надёжность | In-process | Persistent queue/runtime |
| Cleanup safety | Manual/admin bounded CLI | Scheduled safe operational path |
| Production confidence | Compose hardening завершён | VPS smoke + HTTPS + backup flow |

---

## 🐛 Активный технический долг

| Тема | Приоритет | Комментарий |
|------|-----------|-------------|
| In-process `BackgroundTasks` | HIGH | Главный runtime-risk при рестартах |
| Heavy OCR regressions | HIGH | Нет отдельного медленного боевого regression-tier |
| Test warning noise | HIGH | Мешает видеть реальные проблемы |
| Multi-column / ambiguous layouts | HIGH | Требует wave 2 после heavy-tier |
| Production backup/restore | MEDIUM | Нужен operational runbook |

---

## 📚 Документация, которая должна идти в ногу с roadmap

- [x] `README.md` — зафиксирован текущий execution plan и состояние продукта
- [ ] `docs/API.md` — обновить только если появятся новые product-поля или period disambiguation
- [ ] `docs/ARCHITECTURE.md` — обновить при переходе на persistent runtime / queue
- [ ] `docs/CONFIGURATION.md` — обновить при добавлении runtime queue, backup или OCR cache settings

---

*Документ обновляется после каждой завершённой логической волны, а не только по календарю.*
