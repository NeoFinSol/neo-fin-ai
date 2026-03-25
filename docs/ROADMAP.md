# NeoFin AI — Roadmap (Планы развития)

**Дата создания**: 2026-03-25  
**Приоритеты**: HIGH → MEDIUM → LOW

---

## 🚀 Ближайшие спринты (1-4 недели)

### Task 6.1 — OCR Performance Optimization [HIGH]
**Проблема**: OCR 80 страниц = 3-5 минут (pdf2image + tesseract)

**Решения**:
- [ ] Кэширование OCR результатов по hash(PDF)
- [ ] Параллельная обработка страниц (multiprocessing)
- [ ] Снижение DPI для текстовых PDF (200 вместо 300)
- [ ] Прогресс-бар для frontend (WebSocket/SSE)

**Ожидаемый эффект**: 80 страниц за 30-60 секунд

---

### Task 6.2 — Multi-Column PDF Parsing [HIGH]
**Проблема**: Таблицы с 2+ колонками (2022 | 2021) сливаются в одно число

**Решения**:
- [ ] Camelot lattice с Ghostscript (уже установлен)
- [ ] Разделение колонок по ширине символов
- [ ] Выбор первой колонки (текущий год) по умолчанию
- [ ] Явное указание периода в API

**Ожидаемый эффект**: revenue=2.3 трлн вместо 2022

---

### Task 6.3 — Confidence Score Unit Tests [HIGH]
**Файлы**: `tests/test_confidence.py`

**Тесты**:
- [ ] `test_confidence_levels()` — проверка мапы источников
- [ ] `test_filter_by_confidence()` — пороговая фильтрация
- [ ] `test_build_metric()` — создание метрик
- [ ] Property-based: `test_confidence_range()` — [0.0, 1.0]

**Deadline**: 2026-03-27

---

### Task 6.4 — PDF Extractor Pro Tests [MEDIUM]
**Файлы**: `tests/test_pdf_extractor_pro.py`

**Тесты**:
- [ ] `test_extract_metrics_simple_pdf()`
- [ ] `test_extract_metrics_ocr_fallback()`
- [ ] `test_is_text_poor_toc_only()`
- [ ] `test_normalize_number_formats()`

**Deadline**: 2026-03-29

---

## 📅 Среднесрочные планы (1-3 месяца)

### Task 7.1 — Celery + Redis [HIGH]
**Проблема**: BackgroundTasks in-process → задачи теряются при рестарте

**Решение**:
- [ ] Celery worker для обработки PDF
- [ ] Redis как broker + result backend
- [ ] Персистентность статусов задач
- [ ] Retry logic для упавших задач

**Ожидаемый эффект**: Надёжность 99.9%, статус не зависает

---

### Task 7.2 — WebSocket / SSE [MEDIUM]
**Проблема**: Polling 2000ms × N пользователей = нагрузка на БД

**Решение**:
- [ ] WebSocket endpoint `/ws/result/{task_id}`
- [ ] Frontend: замена polling на push-уведомления
- [ ] Fallback на polling для старых браузеров

**Ожидаемый эффект**: Снижение нагрузки на БД в 1000×

---

### Task 7.3 — Frontend Types Cleanup [LOW]
**Проблема**: `types.ts` дублирует `interfaces.ts` с расхождениями

**Решение**:
- [ ] Удалить `types.ts`
- [ ] Обновить все импорты на `interfaces.ts`
- [ ] Добавить TypeScript strict проверку в CI

---

### Task 7.4 — Production Deployment [HIGH]
**Задачи**:
- [ ] Аренда VPS (Selectel / Timeweb / Reg.ru)
- [ ] Настройка Docker Compose production
- [ ] SSL-сертификаты (Let's Encrypt)
- [ ] Мониторинг (Prometheus + Grafana)
- [ ] Backup БД (ежедневный)

**Deadline**: 2026-04-15

---

## 🔮 Долгосрочные планы (3-6 месяцев)

### Task 8.1 — AI Model Fine-Tuning [MEDIUM]
**Цель**: Улучшение качества NLP рекомендаций

**Подход**:
- [ ] Сбор датасета (1000+ отчётов с рекомендациями)
- [ ] Fine-tuning Qwen/DeepSeek
- [ ] Evaluation метрики (relevance, diversity)

---

### Task 8.2 — Industry Benchmarks [MEDIUM]
**Цель**: Отраслевые коэффициенты для скоринга

**Отрасли**:
- [ ] Ритейл (FMCG)
- [ ] Производство
- [ ] IT / SaaS
- [ ] Нефтегаз

**Источник**: Росстат, отраслевые отчёты

---

### Task 8.3 — API-First / White-Label [LOW]
**Цель**: B2B2C модель для банков

**Возможности**:
- [ ] Публичный API документация (Swagger/OpenAPI)
- [ ] Sandbox среда для разработчиков
- [ ] White-label интеграции
- [ ] Tarification (pay-per-call)

---

### Task 8.4 — Mobile App [LOW]
**Платформы**: iOS + Android (React Native / Flutter)

**Функции**:
- [ ] Загрузка PDF с телефона
- [ ] Push-уведомления о готовности
- [ ] Offline режим (кэширование результатов)

---

## 📊 Метрики успеха

| Метрика | Сейчас | Цель (Q2 2026) |
|---------|--------|----------------|
| **Тесты backend** | 578 passed | 700+ passed |
| **Тесты frontend** | 78 passed | 150+ passed |
| **Coverage backend** | 85% | 90%+ |
| **Coverage frontend** | 55% | 75%+ |
| **OCR время (80 стр.)** | 180 сек | 30 сек |
| **API latency (p95)** | 2 сек | 500 мс |
| **Uptime** | N/A | 99.9% |

---

## 🐛 Известные баги (Technical Debt)

| Баг | Приоритет | ETA |
|-----|-----------|-----|
| Multi-column parsing | HIGH | 1 неделя |
| OCR performance | HIGH | 2 недели |
| BackgroundTasks restart | MEDIUM | 1 месяц |
| Polling → WebSocket | MEDIUM | 1 месяц |
| types.ts дублирование | LOW | 2 месяца |

---

## 📚 Документация к обновлению

- [ ] `README.md` — добавить секцию про OCR и confidence scoring
- [ ] `docs/ARCHITECTURE.md` — обновить diagram с pdf_extractor_pro
- [ ] `docs/API.md` — документировать новые поля confidence
- [ ] `INSTALL_WINDOWS.md` — актуализировать версии зависимостей

---

*Документ обновляется каждые 2 недели (спринт-планирование).*
