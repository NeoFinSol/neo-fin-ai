# Runbook финального демо

Этот документ фиксирует повторяемый сценарий показа NeoFin AI на финале конкурса.

## 1. Primary path: локальный показ

### Предусловия
- Заполнен `.env` с рабочими `API_KEY`, `DATABASE_URL`
- Выбран runtime: `TASK_RUNTIME=celery`
- Для финального demo-score включён профиль: `SCORING_PROFILE=retail_demo`
- Локальные PDF-файлы доступны в `PDFforTests`

### Шаги запуска
1. Поднять стек:
```bash
docker compose up -d --build
```
2. Прогнать демо smoke:
```bash
python scripts/demo_smoke.py --base-url http://localhost --api-prefix /api --api-key <API_KEY>
```

### Проверка готовности
- Все три сценария из `tests/data/demo_manifest.json` прошли со статусом `OK`
- Нет `failed/cancelled` в smoke-прогоне
- Задачи видны в `/analyses`

## 2. Backup path: публичный стенд

### Базовый порядок
1. Применить миграции:
```bash
docker compose -f docker-compose.prod.yml run --rm backend-migrate
```
2. Поднять прод-контур:
```bash
docker compose -f docker-compose.prod.yml up -d --build
```
3. Проверить health:
- `GET /api/system/health`

### Smoke на публичном URL
```bash
python scripts/demo_smoke.py --base-url https://<public-host> --api-prefix /api --api-key <API_KEY> --scenario text_single --scenario multi_period_magnit
```

### Минимальный gate
- Публичный URL проходит `text_single` и `multi_period_magnit`
- Если публичный smoke нестабилен, финальный показ переводится на локальный primary path

## 3. Restart sequence (операторский)

При частичном падении сервисов:
1. `backend-migrate` (one-shot, при необходимости после изменений схемы)
2. `db`, `redis`
3. `backend`, `worker`
4. `frontend/nginx`
5. Повторный smoke по одному сценарию (`text_single`)

## 4. Ограничения текущего окна
- HTTPS не блокирует финальный показ, если требует отдельной инфраструктурной итерации
- Этот runbook не включает backup/restore drills, только demo-readiness контур
