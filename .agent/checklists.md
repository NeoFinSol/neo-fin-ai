# Checklists — NeoFin AI

## 1) Чеклист перед коммитом

```
[ ] Код соответствует PEP 8 (ruff/flake8 без ошибок)
[ ] Нет print() — только logger.*()
[ ] Все новые публичные функции имеют type hints и docstring
[ ] Нет закомментированных блоков кода (кроме задокументированных в local_notes.md)
[ ] Если менялся backend-ответ → interfaces.ts обновлён
[ ] Если добавлен новый ratio → RATIO_KEY_MAP обновлён
[ ] Тесты для новой логики написаны и проходят (pytest --run)
[ ] .agent/overview.md и .agent/PROJECT_LOG.md обновлены
[ ] Если менялись Docker-файлы → проверь `docker compose -f docker-compose.prod.yml config` и целевую сборку
[ ] Если менялись production-файлы → проверь .env.example на наличие новых переменных
```

## 2) Validation patterns

| Что изменилось | Что проверить |
|----------------|---------------|
| API payload / schema (`/result/{id}`, `/analyses`, WebSocket events) | Обновить `frontend/src/api/interfaces.ts`, прогнать backend unit/integration тесты по маршрутам, проверить рендер `DetailedReport`/`AnalysisHistory` |
| Новый коэффициент в `ratios.py` | Добавить расчёт в `ratios.py`, учесть в `scoring.py`, добавить ключ в `RATIO_KEY_MAP` (`src/tasks.py`), покрыть тестом |
| Изменения в timeout AI/NLP/REC | Синхронизировать таймауты по связанным файлам, проверить fallback-ветки и отсутствие зависаний |
| Изменения в OCR/PDF extraction | Прогнать тесты extraction/scoring и ручную проверку на текстовом и сканированном PDF |
| Изменения в WebSocket/polling | Проверить гибридную стратегию: WS работает, polling корректно подхватывает fallback |
| Изменения в Docker/prod-конфиге | Локально проверить `docker compose -f docker-compose.prod.yml config`, затем целевую сборку и старт ключевых сервисов |

## 3) Deployment checks

1. Перед деплоем:
   - Убедиться, что новые env-переменные отражены в `.env.example`.
   - Проверить `.dockerignore` и `frontend/.dockerignore` (нет лишних файлов в контексте сборки).
   - Проверить, что backend не запускается от root (`appuser` в `Dockerfile.backend`).
2. Сборка и миграции:
   - Предпочтительный путь: `scripts/deploy-prod.sh`.
   - Альтернатива: `docker compose -f docker-compose.prod.yml build` и затем `docker compose -f docker-compose.prod.yml run --rm backend-migrate`.
3. Smoke-check после старта:
   - Проверить health backend и проксирование через nginx.
   - При `502 Bad Gateway` смотреть `docker-compose logs backend` и health check.
   - При проблемах с миграциями повторить `backend-migrate` вручную.
