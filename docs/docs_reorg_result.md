# Итог реорганизации публичной документации

Дата: 2026-04-20.

## 1. Публичное ядро (остались в репозитории)

- `README.md`
- `frontend/README.md`
- `docs/API.md`
- `docs/ARCHITECTURE.md`
- `docs/CONFIGURATION.md`
- `docs/INSTALL_WINDOWS.md`
- `docs/ROADMAP.md` — возвращён в отслеживаемый контур: строка `docs/ROADMAP.md` удалена из `.gitignore`, файл остаётся в `docs/` для публикации на GitHub
- Служебные мета-документы этой реорганизации: `docs/docs_reorg_plan.md`, `docs/docs_reorg_result.md`

## 2. Публичный архив (остались в репозитории, вынесены из корня `docs/`)

- `docs/archive/README.md` — пояснение структуры архива
- `docs/archive/contest/CONTEST_DEMO_RUNBOOK.md`
- `docs/archive/contest/CONTEST_OPERATOR_CARD.md`
- `docs/archive/contest/contest_presentation_2026/` (включая исходники генератора; локальные `node_modules/` по-прежнему игнорируются вложенным `.gitignore`)

**Важно:** архив остаётся **публичным** на GitHub; он только отделён навигационно от продуктового ядра.

## 3. Удалены из публичного дерева `docs/` после локального сохранения

Следующие файлы **больше не входят** в публичный репозиторий в путях под `docs/` (копии для владельца — в `docs/tech_docs_private/`, см. раздел 4):

- `BUSINESS_MODEL.md`
- `EXTRACTOR_CONFIDENCE_CALIBRATION.md`
- `EXTRACTOR_CONFIDENCE_CALIBRATION_EVIDENCE.md`
- `EXTRACTOR_CONFIDENCE_CALIBRATION_EVIDENCE.json`
- `EXTRACTOR_CONFIDENCE_CALIBRATION_CORPUS.md`
- `MATH_LAYER_V2_WAVE4_CLOSURE.md`
- `public_docs_classification.md`
- `public_docs_gap_audit.md`
- `TECH_DEBT_BACKLOG.md`
- `scoring_freeze_classification.md`
- `scoring_freeze_inventory.md`
- `scoring_freeze_payload_matrix.md`
- `WAVE_4_5_SCORING_FREEZE.md`

## 4. Локальный внутренний контур (не для GitHub)

- **Путь:** `docs/tech_docs_private/` (в репозитории на диске, но **не** в публичном GitHub: каталог в `.gitignore`, по аналогии с `.agent/`).
- **Содержимое:** перечисленные в разделе 3 файлы восстановлены/собраны сюда для владельца рабочей копии.
- **Защита от публикации:** правило `docs/tech_docs_private/` в `.gitignore`. Это не шифрование и не приватность сама по себе — только исключение из коммитов и push в открытый remote.
- **Дальнейшие шаги для владельца:** при необходимости перенести копию в приватный репозиторий или иное хранилище; при свежем `git clone` с GitHub папка появится только после ручного восстановления материалов.

## 5. Исправленные ссылки и навигация

- `README.md` — ядро документации дополнено `docs/ROADMAP.md`; убрана публичная ссылка на `BUSINESS_MODEL.md`; раздел архива указывает на `docs/archive/contest/...`; уточнено назначение каталога `docs/`; добавлено пояснение про материалы вне GitHub и ссылка на этот отчёт
- `AGENTS.md` — из таблицы критичных файлов убрана строка про `docs/BUSINESS_MODEL.md`; добавлен абзац про вынесение внутренних материалов и `docs/tech_docs_private/`
- `docs/archive/contest/contest_presentation_2026/README.md` — относительная ссылка на `content.js`, относительный `cd` для сборки, список источников приведён к новым путям архива и публичному ядру без `BUSINESS_MODEL.md`

Файлы `docs/API.md`, `docs/ARCHITECTURE.md`, `docs/CONFIGURATION.md`, `docs/INSTALL_WINDOWS.md`, `frontend/README.md` **не содержали** ссылок на удалённые документы — правки не потребовались.

## 6. Спорные места для ручного решения

- **Строки в тестах** (`tests/scoring_freeze/helpers/doc_renderers.py` и др.), где в тексте фигурируют пути вида `` `docs/scoring_freeze_*.md` ``: файлы из `docs/` удалены; если эти строки попадают в снапшоты или внешние проверки, может понадобиться отдельная правка тестов или формулировок — в рамках текущей задачи код не менялся.
- **Содержимое `docs/tech_docs_private/`:** не коммитить и не пушить (`git add -f` для этого каталога использовать нельзя).

## 7. Дополнение после первого пуша (`merge: origin/main`)

Перед успешным `git push` на `origin/main` уже лежал отдельный коммит с правками в `docs/TECH_DEBT_BACKLOG.md` и повторным появлением freeze-артефактов под `docs/` (`WAVE_4_5_SCORING_FREEZE.md`, `scoring_freeze_*.md`).

При слиянии с `origin/main` (merge-коммит `961bf2c`) сделано следующее:

- актуальное **содержимое** этих файлов с ветки по умолчанию на GitHub скопировано в **`docs/tech_docs_private/`** (перезапись локальных копий там, где применимо);
- сами пути **`docs/TECH_DEBT_BACKLOG.md`**, **`docs/WAVE_4_5_SCORING_FREEZE.md`**, **`docs/scoring_freeze_*.md`** в отслеживаемом дереве **снова не оставлены** — публичный контур `docs/` по-прежнему без этих файлов.

Имеет смысл при следующем `git pull` смотреть на подобные конфликты так же: новые версии — в `docs/tech_docs_private/`, публичный `docs/` — только ядро и архив из разделов 1–2.
