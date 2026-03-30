# План Следующей Сессии (2026-03-29)

## Ближайшие цели
1. Закрыть оставшиеся дыры в извлечении баланса на scanned PDF, чтобы ключевые поля не падали в `None` без реальной причины.
2. Ужесточить инварианты качества извлечения, чтобы исключить ложноположительные “красивые” числа.
3. Расширить real-fixture regression контур, чтобы правки не откатывали точность на реальных отчётах.

## Пакеты правок (приоритет)
1. `P1 (Recommended)` — унифицировать layout-aware извлечение строк с кодами `1200/1210/1230/1250/1400/1500`.
   - Класс: `bug-investigation`
   - Файлы: `src/analysis/pdf_extractor.py`, `tests/test_pdf_extractor.py`
2. `P2` — добить `long_term_liabilities (1400)` и безопасный derive `liabilities = long_term + short_term`, где это надёжнее.
   - Класс: `cross-module`
   - Файлы: `src/analysis/pdf_extractor.py`, `tests/test_pdf_local_magnit_regression.py`
3. `P3` — единый post-parse guardrail-блок для form-like OCR (`component <= subtotal`, `subtotal <= total`, soft-null для сомнительных значений).
   - Класс: `cross-module`
   - Файлы: `src/analysis/pdf_extractor.py`, `tests/test_pdf_extractor.py`
4. `P4` — расширить local real-fixture regression минимум на 2 scanned-кейса и зафиксировать значения `inventory/AR/STL/LTL`.
   - Класс: `local-low-risk`
   - Файлы: `tests/test_pdf_local_magnit_regression.py`
5. `P5` — performance-pass OCR: запуск row-crop OCR только по сигналу формы и только для релевантных строк, чтобы не раздувать latency.
   - Класс: `cross-module`
   - Файлы: `src/analysis/pdf_extractor.py`, `tests/test_pdf_extractor.py`

## Стартовый Промт Для Следующей Сессии
```text
Продолжаем работу над основным проектом E:\neo-fin-ai.

Сначала перечитай:
- E:\neo-fin-ai\AGENTS.md
- E:\neo-fin-ai\.agent\overview.md
- E:\neo-fin-ai\.agent\local_notes.md
- E:\neo-fin-ai\.agent\PROJECT_LOG.md
- E:\neo-fin-ai\.agent\architecture.md
- E:\neo-fin-ai\.agent\checklists.md
- E:\neo-fin-ai\.agent\modes.md
- E:\neo-fin-ai\.agent\subagents\README.md
- E:\neo-fin-ai\docs\ARCHITECTURE.md
- E:\neo-fin-ai\docs\BUSINESS_MODEL.md
- E:\neo-fin-ai\docs\ROADMAP.md
- E:\neo-fin-ai\docs\API.md
- E:\neo-fin-ai\frontend\src\api\interfaces.ts
- E:\neo-fin-ai\src\tasks.py
- E:\neo-fin-ai\docs\NEXT_SESSION_PLAN.md

Важно:
- строго соблюдай orchestration rules из AGENTS.md
- если задача не local-low-risk: classify → delegate → wait → synthesize → implement
- после каждого пакета уровня cross-module и выше обязателен явный code_review pass

Цель текущей сессии: начать с P1 из NEXT_SESSION_PLAN.md и довести пакет до commit-ready состояния (код + тесты + синхронизация агентских мета-файлов).
```
