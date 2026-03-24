# Requirements Document

## Introduction

NeoFin AI Competition Release — финальный этап подготовки веб-приложения NeoFin AI к конкурсу «Молодой финансист 2026». Фича закрывает четыре gap-а между текущим MVP и требованиями конкурса: добавление confidence score для извлечённых данных, поддержка многопериодного анализа с визуализацией динамики, полная техническая и бизнес-документация, а также production-ready деплой через Docker Compose.

Существующая архитектура (FastAPI + React/Mantine, layered: routers → tasks → analysis pipeline → ai_service → db/crud) остаётся неизменной. Все изменения вписываются в текущие слои без нарушения архитектурных ограничений.

---

## Glossary

- **System** — веб-приложение NeoFin AI в целом (backend + frontend).
- **Extractor** — модуль `src/analysis/pdf_extractor.py`, извлекающий финансовые показатели из PDF.
- **Confidence_Score** — числовое значение от 0.0 до 1.0, отражающее уверенность Extractor в корректности извлечённого показателя.
- **Confidence_Threshold** — минимальное значение Confidence_Score, ниже которого показатель считается ненадёжным. Значение по умолчанию: 0.5.
- **Extraction_Source** — строковое описание метода извлечения показателя, используемое для explainability. Одно из: `"table_exact"`, `"table_partial"`, `"text_regex"`, `"derived"`.
- **Extraction_Metadata** — структура `{"value": float | None, "confidence": float, "source": Extraction_Source}`, возвращаемая Extractor для каждого показателя.
- **Explainability_Block** — UI-элемент (tooltip), отображающий для каждого показателя: числовое значение, Confidence_Score и Extraction_Source в человекочитаемом виде.
- **Pipeline** — последовательность обработки: Extractor → ratios → scoring → recommendations → nlp_analysis.
- **Period** — один финансовый период, соответствующий одному загруженному PDF-файлу с указанием года/квартала.
- **Multi_Period_Analysis** — анализ нескольких Period-ов в рамках одной сессии для построения динамики показателей.
- **Trend_Chart** — интерактивный график динамики финансовых коэффициентов по нескольким Period-ам.
- **Session** — набор из 1–5 Period-ов, загруженных пользователем для Multi_Period_Analysis.
- **RATIO_KEY_MAP** — словарь маппинга русских ключей коэффициентов в английские, определённый в `src/tasks.py`.
- **AnalysisData** — интерфейс данных анализа, определённый в `frontend/src/api/interfaces.ts`.
- **Production_Build** — сборка приложения, готовая к развёртыванию в production-среде.
- **Docker_Compose** — файл `docker-compose.prod.yml` для production-развёртывания.
- **Nginx** — веб-сервер, обслуживающий frontend и проксирующий запросы к backend в production.

---

## Requirements

### Requirement 1: Confidence Score и Explainability извлечения данных

**User Story:** Как член жюри конкурса, я хочу видеть уверенность модели в извлечённых данных и источник каждого показателя, чтобы оценить надёжность анализа, отфильтровать потенциально некорректные данные и понять, как именно система приняла решение.

#### Acceptance Criteria

1. WHEN Extractor извлекает финансовый показатель из PDF, THE Extractor SHALL вычислить Confidence_Score от 0.0 до 1.0 для каждого показателя на основе метода извлечения (таблица с явным совпадением ключевого слова — высокая уверенность; текстовый regex — средняя; производный расчёт — низкая).
2. THE Extractor SHALL возвращать Extraction_Metadata `{"value": float | None, "confidence": float, "source": str}` для каждого из 15 финансовых показателей вместо простого `float | None`.
3. THE Extractor SHALL присваивать Extraction_Source по следующей шкале: `"table_exact"` (точное совпадение ключевого слова в таблице) — Confidence_Score 0.9; `"table_partial"` (частичное совпадение в таблице) — 0.7; `"text_regex"` (извлечение из текста через regex) — 0.5; `"derived"` (производный расчёт, например liabilities = assets − equity) — 0.3.
4. WHEN Confidence_Score показателя ниже Confidence_Threshold, THE Pipeline SHALL исключить этот показатель из расчёта коэффициентов, подставив `None` вместо значения.
5. THE System SHALL использовать Confidence_Threshold со значением по умолчанию 0.5, настраиваемым через переменную окружения `CONFIDENCE_THRESHOLD`.
6. WHEN анализ завершён, THE System SHALL включить поле `extraction_metadata` в ответ API, содержащее словарь `{metric_key: {"confidence": float, "source": str}}` для всех 15 показателей.
7. WHEN пользователь просматривает результат анализа, THE System SHALL отображать цветной индикатор Confidence_Score рядом с каждым финансовым показателем: зелёный (🟢) при Confidence_Score > 0.8, жёлтый (🟡) при 0.5–0.8, красный (🔴) при < 0.5.
8. WHEN пользователь наводит курсор на индикатор Confidence_Score показателя, THE System SHALL отобразить Explainability_Block (tooltip) со структурированным содержимым: «Источник: [таблица / текст / расчёт]», «Метод: [точное совпадение / частичное совпадение / regex / производный]», «Уверенность: [высокая / средняя / низкая]».
9. IF Confidence_Score показателя ниже Confidence_Threshold, THEN THE System SHALL визуально выделить этот показатель предупреждающим индикатором (🔴) и применить приглушённый стиль к строке показателя в UI.
10. FOR ALL финансовых показателей, Confidence_Score SHALL быть числом в диапазоне [0.0, 1.0] включительно.
11. THE System SHALL отображать в нижней части раздела метрик сводную строку: «Извлечено надёжно: N из 15 показателей» (где N — количество показателей с Confidence_Score ≥ Confidence_Threshold).
12. THE System SHALL отображать один раз в разделе метрик информационный hint: «Показатели с низкой уверенностью (🔴) могут быть исключены из расчёта коэффициентов».

---

### Requirement 2: Многопериодный анализ и визуализация динамики

**User Story:** Как пользователь системы, я хочу загрузить отчётность за несколько периодов и увидеть динамику финансовых коэффициентов на графике, чтобы оценить тренды развития компании за последние 3 года.

#### Acceptance Criteria

1. THE System SHALL поддерживать загрузку от 1 до 5 PDF-файлов в рамках одной Session для Multi_Period_Analysis.
2. WHEN пользователь загружает несколько PDF, THE System SHALL запросить у пользователя метку периода (год или квартал/год) для каждого файла в формате строки длиной не более 20 символов.
3. THE System SHALL обрабатывать каждый PDF из Session независимо через существующий Pipeline, сохраняя результаты с привязкой к метке периода.
4. WHEN все PDF в Session обработаны, THE System SHALL предоставить эндпоинт `POST /multi-analysis` для запуска Multi_Period_Analysis и `GET /multi-analysis/{session_id}` для получения результатов.
5. THE System SHALL возвращать из `GET /multi-analysis/{session_id}` структуру, содержащую массив периодов с коэффициентами и метаданными для построения Trend_Chart.
6. WHEN результаты Multi_Period_Analysis доступны, THE System SHALL отображать Trend_Chart на отдельной вкладке страницы DetailedReport с возможностью выбора отображаемых коэффициентов.
7. THE Trend_Chart SHALL отображать динамику не менее 13 коэффициентов из RATIO_KEY_MAP по оси X (периоды) и оси Y (значения коэффициентов).
8. WHEN пользователь выбирает коэффициент на Trend_Chart, THE System SHALL выделить соответствующую линию и отобразить числовые значения для каждого периода.
9. IF для периода коэффициент равен `None` (данные не извлечены), THEN THE Trend_Chart SHALL отобразить разрыв линии в этой точке без ошибки рендеринга.
10. THE System SHALL сохранять результаты Multi_Period_Analysis в базе данных PostgreSQL с возможностью последующего получения через `GET /multi-analysis/{session_id}`.
11. WHILE Multi_Period_Analysis выполняется, THE System SHALL возвращать статус `"processing"` с прогрессом в формате `{completed: N, total: M}` при запросе `GET /multi-analysis/{session_id}`.
12. FOR ALL Session с несколькими периодами, THE System SHALL сортировать периоды по хронологическому порядку на Trend_Chart независимо от порядка загрузки.

---

### Requirement 3: Техническая и бизнес-документация

**User Story:** Как член жюри конкурса, я хочу получить полную документацию по системе, чтобы оценить техническую зрелость проекта, понять архитектуру и бизнес-модель.

#### Acceptance Criteria

1. THE System SHALL содержать файл `README.md` в корне репозитория с разделами: описание проекта, требования к окружению, инструкция по установке (не более 5 шагов), инструкция по запуску (dev и production), описание основных возможностей.
2. THE System SHALL содержать файл `docs/CONFIGURATION.md` с описанием всех переменных окружения, включая: имя переменной, тип, значение по умолчанию, описание назначения, пометку об обязательности.
3. THE System SHALL содержать файл `docs/ARCHITECTURE.md` с описанием: layered-архитектуры (routers → tasks → pipeline → ai_service → db/crud), data flow от загрузки PDF до отображения результата, описания каждого модуля в `src/analysis/` и `src/core/`, диаграммы в формате ASCII или Mermaid.
4. THE System SHALL содержать файл `docs/API.md` с описанием всех эндпоинтов: метод, путь, параметры запроса, формат тела запроса, формат ответа, коды ошибок, примеры curl-запросов.
5. THE System SHALL содержать файл `docs/BUSINESS_MODEL.md` с описанием: целевой аудитории, ценностного предложения, модели монетизации, конкурентных преимуществ, плана развития на 12 месяцев.
6. THE README.md SHALL содержать команду запуска production-среды одной строкой через Docker Compose.
7. THE docs/API.md SHALL содержать описание новых эндпоинтов `POST /multi-analysis` и `GET /multi-analysis/{session_id}`, добавленных в Requirement 2.
8. THE docs/CONFIGURATION.md SHALL содержать описание переменной `CONFIDENCE_THRESHOLD`, добавленной в Requirement 1.

---

### Requirement 4: Production Build и деплой

**User Story:** Как разработчик, я хочу развернуть NeoFin AI в production одной командой, чтобы продемонстрировать работающую систему жюри конкурса.

#### Acceptance Criteria

1. THE System SHALL содержать файл `docker-compose.prod.yml` с сервисами: `backend` (FastAPI), `frontend` (Nginx + production build), `db` (PostgreSQL 16), без сервисов разработки (db_test, hot-reload).
2. THE Docker_Compose SHALL использовать multi-stage Dockerfile для frontend: stage `build` (Node.js + Vite build), stage `serve` (Nginx, только статика).
3. THE Docker_Compose SHALL использовать multi-stage Dockerfile для backend: stage `build` (установка зависимостей), stage `runtime` (минимальный образ без dev-зависимостей).
4. THE Nginx SHALL проксировать запросы `/api/*` к backend-сервису и обслуживать статические файлы frontend с корректными заголовками кэширования.
5. THE Docker_Compose SHALL поддерживать SSL-ready конфигурацию: Nginx SHALL читать сертификаты из volume `/etc/nginx/certs`, при отсутствии сертификатов — работать по HTTP без ошибки запуска.
6. THE System SHALL содержать скрипт `scripts/start-prod.sh`, запускающий production-среду командой `./scripts/start-prod.sh` и выполняющий: проверку наличия `.env` файла, запуск `docker-compose.prod.yml`, применение миграций Alembic.
7. WHEN production-среда запущена, THE System SHALL быть доступна на порту 80 (HTTP) без дополнительной настройки.
8. THE Docker_Compose SHALL определять health check для сервиса `backend` через `GET /health` с интервалом 30 секунд и таймаутом 10 секунд.
9. THE Docker_Compose SHALL определять health check для сервиса `db` через `pg_isready` с интервалом 10 секунд.
10. IF переменная окружения `SSL_CERT_PATH` задана, THEN THE Nginx SHALL включить HTTPS на порту 443 и перенаправлять HTTP на HTTPS.
11. THE production build frontend SHALL быть оптимизирован: code splitting по маршрутам, минификация JS/CSS, gzip-сжатие через Nginx.
12. THE System SHALL содержать файл `.env.example` с примерами всех обязательных переменных окружения для production-развёртывания.

---

### Requirement 5: Тестовое покрытие новой функциональности

**User Story:** Как разработчик, я хочу иметь тесты для всех новых модулей, чтобы обеспечить надёжность системы и соответствие стандартам конкурса.

#### Acceptance Criteria

1. THE System SHALL содержать тесты для логики вычисления Confidence_Score в `src/analysis/pdf_extractor.py` с покрытием всех четырёх уровней уверенности (0.9, 0.7, 0.5, 0.3).
2. THE System SHALL содержать property-тест (hypothesis): FOR ALL наборов финансовых показателей с Confidence_Score, фильтрация по Confidence_Threshold SHALL исключать только показатели с Confidence_Score строго ниже порога.
3. THE System SHALL содержать тесты для эндпоинтов `POST /multi-analysis` и `GET /multi-analysis/{session_id}`, проверяющие корректность статусов, структуру ответа и обработку ошибок.
4. THE System SHALL содержать тесты для логики сортировки периодов в Multi_Period_Analysis, проверяющие хронологический порядок при произвольном порядке загрузки.
5. THE System SHALL содержать frontend-тесты (vitest) для компонента Trend_Chart, проверяющие корректный рендеринг при наличии `None`-значений в данных периодов.
6. WHEN все тесты запущены командой `pytest`, THE System SHALL показывать 0 failed тестов.
7. THE System SHALL содержать property-тест (hypothesis): FOR ALL валидных PDF-метрик, Confidence_Score SHALL быть числом в диапазоне [0.0, 1.0].
