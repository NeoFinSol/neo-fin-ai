# Дорожная карта NeoFin AI

## Текущий приоритет (финал конкурса, окно 3-5 дней)

### Пакет A — Demo Corpus Lock
- Зафиксировать 3 эталонных сценария: `text`, `scanned`, `multi-period`
- Закрепить headline-метрики и допуски в `tests/data/demo_manifest.json`
- Держать эти сценарии в связке с локальным regression path

### Пакет B — Local Demo Smoke Automation
- Повторяемый smoke path для полного цикла: upload -> processing -> completed -> history
- Основной runtime для показа: `TASK_RUNTIME=celery`
- Скрипты запуска: `scripts/demo_smoke.py`, `scripts/run_demo_smoke.ps1`, `scripts/run_demo_smoke.sh`

### Пакет C — Report Screen Execution Polish
- Разделить `DetailedReport` на подкомпоненты
- Вынести frontend constants и helper-логику
- Убрать `Math.random()` из transaction ID

### Пакет D — Public Backup Stand
- Подготовить резервный публичный контур на compose-схеме с `worker + redis`
- Зафиксировать операторский порядок `migrate -> up -> health -> demo`
- HTTPS оставить как post-final hardening, если нужна отдельная инфраструктурная итерация

### Пакет E — Rehearsal & Contest Readiness
- Провести 2 репетиции: локальный primary и публичный backup
- Утвердить операторскую карточку показа и fallback-переход

## После финала (следующая волна)
- Production hardening: HTTPS, backup/restore, VPS hardening checks
- Cleanup operationalization: cron/Task Scheduler runbook, retention review
- Дополнительный performance-pass для тяжёлых real-PDF кейсов
- Interactive OCR corrections и продуктовые расширения
- S3/MinIO, отраслевые benchmarks/OKVED
