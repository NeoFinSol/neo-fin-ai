# Validated Backlog По Отчёту KimiK2.5

**Дата валидации:** 2026-03-30  
**Источник:** `docs/KimiK2.5_report.md`  
**Принцип:** в backlog попали только пункты, подтверждённые текущим кодом.

---

## 1) Что НЕ брать как critical из отчёта

1. `docker-compose.yml: +services` — **не подтверждено** (в файле уже `services:`).
2. `healthcheck без curl` — **не подтверждено** (`curl` уже установлен в `Dockerfile.backend`).
3. `TESTING: 0` всегда truthy — **не подтверждено** для текущего backend-кода (проверка идёт через `== "1"`).
4. `redis:8.6-alpine` как “несуществующая версия” — **не подтверждено в проекте** (runtime ранее фиксировался как рабочий).

---

## 2) Подтверждённые и полезные цели

1. `DetailedReport.tsx` остаётся крупным и перегруженным.
2. Во frontend есть `CONFIDENCE_THRESHOLD`, `TOTAL_METRICS` и `Math.random()` в продуктовой странице.
3. В extractor остаются жёстко зашитые константы (например `MAX_OCR_PAGES`), которые лучше вынести в настройки.
4. В фронтенде одновременно используются две chart-библиотеки (`recharts` и `@mantine/charts`).
5. Полезно документировать и постепенно сокращать magic numbers в extraction-пайплайне.

---

## 3) Очищенный backlog (ближайшие пакеты)

## P1 — Frontend decomposition: `DetailedReport`
**Класс:** `cross-module`  
**Цель:** разделить страницу на подкомпоненты и вынести вычислительную логику из JSX.

**Объём:**
- Разбить `DetailedReport.tsx` минимум на:
  - `MetricsGrid`
  - `ScoringSection`
  - `RiskFactorsSection`
- Вынести расчёты/мапперы в `frontend/src/utils/`.

**Definition of Done:**
- Страница визуально и функционально не изменилась.
- Снижен объём главного файла.
- Добавлены targeted tests для вынесенных функций (если они детерминированы).

## P2 — Frontend constants & transaction id hygiene
**Класс:** `cross-module`  
**Цель:** убрать хардкод и заменить слабый `Math.random()` путь.

**Объём:**
- `CONFIDENCE_THRESHOLD` и `TOTAL_METRICS` перенести в единый frontend config/constants слой.
- `transactionId` перевести на более корректный генератор (`crypto.randomUUID()` с fallback).

**Definition of Done:**
- Нет использования `Math.random()` для transaction id.
- Константы используются из одного места.

## P3 — Config-driven extractor limits
**Класс:** `cross-module`  
**Цель:** вынести runtime-ограничения extraction/OCR в settings.

**Объём:**
- Перенести `MAX_OCR_PAGES` и соседние лимиты в `AppSettings`/env.
- Добавить валидацию диапазонов + дефолты.
- Обновить docs (`docs/CONFIGURATION.md`).

**Definition of Done:**
- Лимиты читаются из настроек, не захардкожены в модуле.
- Есть тесты валидации конфигов и smoke-проверка extraction path.

## P4 — Chart stack consolidation
**Класс:** `local-low-risk` (если без UI-поведения), иначе `cross-module`  
**Цель:** убрать дубли chart-экосистемы и снизить сложность поддержки.

**Объём:**
- Принять один стек диаграмм (рекомендовано Mantine-first для консистентности UI).
- Удалить неиспользуемую библиотеку и привести импорты.

**Definition of Done:**
- В `package.json` остаётся один chart stack.
- Сборка и ключевые страницы отчёта проходят без регрессий.

## P5 — Magic-number documentation pass
**Класс:** `local-low-risk`  
**Цель:** документировать неизбежные эвристики extraction-пайплайна.

**Объём:**
- Для ключевых эвристик добавить короткие комментарии “почему”.
- Вынести список критичных чисел и их смысл в `docs/ARCHITECTURE.md` или `docs/CONFIGURATION.md`.

**Definition of Done:**
- Для основных эвристик есть объяснение причин.
- Снижен риск случайной деградации при будущих правках.

---

## 4) Рекомендуемый порядок выполнения

1. `P1` (decomposition `DetailedReport`)
2. `P2` (constants + transaction id)
3. `P3` (config-driven extractor limits)
4. `P4` (chart stack consolidation)
5. `P5` (magic-number docs pass)

