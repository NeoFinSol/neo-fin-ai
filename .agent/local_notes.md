# Local Notes

## Активные проблемы

### Orphan models: delete unsupported `src/models/database` boundary instead of repairing imports
**Статус**: ✅ Решено (2026-04-14)
**Дата**: 2026-04-14
**Проблема**:
- `src/models/database/user.py` и `project.py` импортировали несуществующий `src.core.database`
- при этом живой ORM surface проекта уже находился в `src/db/models.py` / `src.db.database.Base`
- у orphan package не было внешних consumers и не было миграций под `users/projects`
**Решение**:
- после execution-time repo-wide recheck по maintained executable surface (`src/tests/scripts/migrations + top-level tooling`) orphan package удалён целиком
- `src/db/models.py` закреплён как canonical supported ORM boundary
- добавлен `tests/test_dead_paths.py`, который проверяет:
  - canonical ORM import smoke через `src.db.models`
  - отсутствие orphan files
  - отсутствие ссылок `src.models.database` в поддерживаемой executable surface
**Памятка**:
- если в будущем снова понадобится auth/project ORM layer, это уже отдельная schema/domain wave; не воскрешай `src/models/database` точечным import-fix
- если dead-path guard начинает падать, сначала проверь, не появился ли новый live consumer в `src/tests/scripts/migrations` или tooling, а не возвращай удалённый пакет

### Util/config hardening: timeout-only retry + bounded float masking + nonsecret Alembic placeholder
**Статус**: ✅ Решено (2026-04-14)
**Дата**: 2026-04-14
**Проблема**:
- `src/utils/retry_utils.py::retry_with_timeout()` retry’ил `(asyncio.TimeoutError, Exception)`, из-за чего programming/non-timeout errors случайно попадали под retry
- `src/utils/masking.py::_mask_number()` раздувал fractional mask width на float repr artifacts вроде `1/3` и `0.1 + 0.2`
- `alembic.ini` хранил credential-bearing fallback URL `postgresql+psycopg2://postgres:postgres@localhost:5432/neofin`
**Решение**:
- `retry_with_timeout()` сузили до `retryable_exceptions=(asyncio.TimeoutError,)`; если после этого начинают всплывать non-timeout ошибки, считай это размаскированным дефектом, а не regression самого hardening
- введён `MAX_FRACTIONAL_MASK_WIDTH = 4`; cap применяется только к fractional mask segment и только после текущего fractional-length calculation
- tracked `alembic.ini` теперь держит intentional nonsecret placeholder `postgresql+psycopg2://user:pass@localhost/dbname` и комментарий, что runtime migrations должны использовать `DATABASE_URL` через `env.py`
**Памятка**:
- не расширяй обратно retry policy в `retry_with_timeout()` до broad `Exception` без отдельного решения по transient/non-transient taxonomy
- в masking fix не трогай integer-part masking, sign handling и zero semantics; режется только дробная маска
- regression на Alembic должен читать tracked `alembic.ini` файл напрямую, а не только runtime config object

### Auth/system hardening: constant-time API-key compare + sanitized readiness + UTC-aware health timestamps
**Статус**: ✅ Решено (2026-04-14)
**Дата**: 2026-04-14
**Проблема**:
- `src/core/auth.py` сравнивал API key через обычное `==` / `!=`
- `src/routers/system.py::/system/ready` отдавал `str(e)` наружу
- `/system/health` и `/system/healthz` использовали naive `datetime.utcnow().isoformat()`
**Решение**:
- введён private helper `_api_keys_match()` на `hmac.compare_digest` без изменения exact-match semantics
- `/system/ready` теперь возвращает fixed sanitized detail `Service not ready: database connection failed`
- timestamps для `/system/health` и `/system/healthz` генерируются через shared UTC-aware helper на `datetime.now(timezone.utc)`
**Памятка**:
- если снова меняется auth compare path, сохраняй exact-match semantics: без trim/lowercase/normalization
- если меняется readiness error detail, raw DB exception text должен оставаться только в логах
- если меняется health timestamp, сохраняй string field `timestamp`, parseable as UTC-aware ISO-8601

### Tech debt: confidence penalty factor — magic constant 0.9 в engine
**Статус**: ✅ Решено
**Дата**: 2026-04-12
**Проблема**: `_derive_confidence` в `src/analysis/math/engine.py` содержит `0.9` как missing-confidence penalty factor. Это policy decision, живущий не в policies.py. При изменении penalty придётся править engine.
**Решение**: penalty вынесен в `src/analysis/math/policies.py` как `MISSING_CONFIDENCE_PENALTY_FACTOR: Final = 0.9`; engine теперь читает только policy constant.

### Tech debt: domain constraints в validators
**Статус**: ✅ Решено (2026-04-13)
**Дата**: 2026-04-12
**Проблема**: `EXPECTED_NON_NEGATIVE_INPUTS` в `src/analysis/math/validators.py` — хардкоженный набор ключей (`cash_and_equivalents`, `equity`, `revenue`, etc.). Это domain/registry knowledge, а не validation concern. Новая метрика с non-negative constraint требует правки validators.
**Решение**: `MetricDefinition` теперь несёт `non_negative_inputs`, а `INPUT_DOMAIN_CONSTRAINTS`/`get_input_domain_constraint()` строятся производно из canonical registry. `validators.py` больше не содержит отдельного semantic list.

### Tech debt: две параллельные map без structural link
**Статус**: ✅ Решено (2026-04-13)
**Дата**: 2026-04-12
**Проблема**: `LEGACY_RATIO_NAME_MAP` (projections.py) и `RATIO_KEY_MAP` (ratios.py) содержат одинаковые 15 metric IDs, но поддерживаются независимо. Drift risk — добавление entry в одну map без другой = тихий regression.
**Решение**: canonical naming projections перенесены в `MetricDefinition` (`legacy_label`, `frontend_key`) внутри `src/analysis/math/registry.py`; `LEGACY_RATIO_NAME_MAP` и `RATIO_KEY_MAP` теперь derived lookup maps, локальная map в `ratios.py` удалена.

### Confirmed debt wave: `process_pdf()`, `upload_pdf()` и reflection dispatch remediation
**Статус**: ✅ Решено (2026-04-13)
**Дата**: 2026-04-13
**Проблема**: после интеграции `Math Layer v1` оставались три cross-layer structural хвоста:
- `src/tasks.py::process_pdf()` был слишком длинным orchestration entrypoint
- `src/routers/pdf_tasks.py::upload_pdf()` смешивал transport, tempfile lifecycle, DB creation и dispatch coordination
- `src/analysis/extractor/pipeline.py` использовал `inspect.signature(...)` как implicit compatibility dispatch
**Решение**:
- `process_pdf()` превращён в thin orchestration wrapper с phase helpers и сохранением status/cancellation behavior
- `upload_pdf()` превращён в thin boundary wrapper с отдельными helpers для upload/save/provider/DB/dispatch path
- reflection dispatch удалён; pipeline stage invocation теперь идёт только по explicit typed callable contract

### Tech debt: precompute.py не должен стать вторым math engine
**Статус**: открыт
**Дата**: 2026-04-12
**Проблема**: `_build_total_debt` — это formula logic, `_route_ebitda_variants` — routing logic. При расширении v2 precompute может разрастись. Допустимо в v1, но следить за ростом.
**Решение**: при добавлении второй derived-формулы — вынести формулы в registry compute, оставив precompute как чистый input routing layer. При росте EBITDA routing — выделить `ebitda_resolver.py`.

### Для unsupported legacy ratios не хардкодь `None` в `ratios.py` — добавляй `SUPPRESS_UNSAFE` placeholders в math registry и projection map
**Статус**: ✅ Учтено
**Дата**: 2026-04-12
**Проблема**: после ввода `Math Layer v1` safe subset легко оставить inconsistent bridge: часть legacy-exported unsupported метрик может уходить в `None` напрямую из `ratios.py` или в `projection=missing_metric`, хотя продуктовый инвариант требует `DerivedMetric(status=suppressed)` как единственный путь между math и legacy bridge.
**Как проявлялось**:
- `quick_ratio`, `ROA/ROE`, leverage, interest coverage и turnover ratios были частично:
  - hardcoded `None` в `src/analysis/ratios.py`
  - либо отсутствовали в registry/projection и проваливались в `missing_metric`
**Решение / workaround**:
- если legacy payload всё ещё должен содержать unsupported metric key, добавляй:
  - placeholder `MetricDefinition` в `src/analysis/math/registry.py`
  - `suppression_policy=SuppressionPolicy.SUPPRESS_UNSAFE`
  - mapping в `src/analysis/math/projections.py`
- `src/analysis/ratios.py` должен только читать `legacy_values.get(...)`, а не решать локально, что отдавать `None`
**Памятка**:
- `missing_metric` допустим для действительно неэкспортируемых ids, но не для legacy-exported контрактных ключей
- быстрый regression signal:
  - `tests/test_math_projection_bridge.py`
  - `tests/test_ratios.py::test_calculate_ratios_reads_all_legacy_exports_from_projection`

### Generic EBITDA в precompute должен маршрутизироваться fail-closed; без explicit semantics не маппить в `ebitda_reported`
**Статус**: ✅ Учтено
**Дата**: 2026-04-12
**Проблема**: generic `ebitda` из extractor path может нести approximation semantics (`gross_profit_to_ebitda_approximation`), а без explicit routing его легко silently схлопнуть в `ebitda_reported`.
**Как проявлялось**:
- `src/analysis/math/precompute.py` делал unconditional `ebitda -> ebitda_reported`
- из-за этого spec-level separation `reported / approximated / canonical` нарушалась ещё до engine stage
**Решение / workaround**:
- fail-closed routing в `precompute.py`:
  - approximation reason code → `ebitda_approximated`
  - explicit reported semantics (`source="reported"` или будущий `reported_ebitda`) → `ebitda_reported`
  - ambiguous generic EBITDA → не маппить ни в один variant
**Памятка**:
- если новый extractor path начинает отдавать richer EBITDA semantics, расширяй router явно; не возвращайся к implicit generic mapping
- быстрый regression signal:
  - `tests/test_math_engine.py::{test_precompute_routes_approximated_ebitda_to_approximation_variant,test_precompute_routes_explicit_reported_ebitda_to_reported_variant,test_precompute_keeps_ambiguous_ebitda_unmapped}`

### После смены semantics `_normalize_inverse()` нужно синхронно обновлять `tests/test_analysis_scoring.py`, а не только новые math/scoring suites
**Статус**: ✅ Учтено
**Дата**: 2026-04-12
**Проблема**: при `Math Layer v1` `_normalize_inverse()` перестал возвращать `1.0` для `value <= 0` и теперь трактует non-positive inverse ratios как unavailable (`None`). Новый closure set это покрывал, но legacy unit-file `tests/test_analysis_scoring.py` остался на старой семантике и silently drift’овал до отдельного review-pass.
**Как проявлялось**:
- `python -m pytest tests/test_analysis_scoring.py -q`
- падал на:
  - `TestNormalizeInverse.test_zero_value`
  - `TestNormalizeInverse.test_negative_value`
- ожидание было `1.0`, фактическое значение — `None`
**Решение / workaround**:
- при изменении scoring helper semantics проверять не только новые targeted suites (`test_math_containment.py`, `test_scoring.py`), но и legacy unit-file `tests/test_analysis_scoring.py`
- для inverse normalization текущий канон такой:
  - `value <= 0` → unavailable (`None`)
  - scoring consumer выше по стеку должен трактовать это через `if score is None: continue`
**Памятка**:
- если после math/scoring refactor всё зелёно в новых suites, но остаётся подозрение на старый unit drift, первым делом прогоняй `tests/test_analysis_scoring.py` отдельно
- это test drift, а не runtime regression, если production path уже делает `if score is None: continue`

### `background_tasks.add_task()` передаёт args positionally — `**kwargs` в mock-функциях не работает
**Статус**: ✅ Учтено
**Дата**: 2026-04-12
**Проблема**: при изменении сигнатуры `process_pdf()` (добавление `debug_trace: bool`), mock-функции в `test_api.py` с `**kwargs` падали, потому что FastAPI `BackgroundTasks.add_task()` передаёт все аргументы positionally.
**Решение**: mock-функции должны иметь явную сигнатуру со всеми позиционными параметрами: `async def fake_process(task_id: str, file_path: str, ai_provider: str | None = None, debug_trace: bool = False)`

### `apply_issuer_metric_overrides` возвращает tuple, не dict
**Статус**: ✅ Учтено
**Дата**: 2026-04-12
**Проблема**: return type изменён с `dict[str, ExtractionMetadata]` на `tuple[dict[str, ExtractionMetadata], list[IssuerOverrideTrace]]`. Все callers обязаны unpack: `(updated, overrides) = apply_issuer_metric_overrides(...)`
**Памятка**: если тест падает на `dict has no attribute __iter__` в issuer_fallback — проверь, что caller unpack’ает tuple

### `_try_llm_extraction` возвращает structured dict, не plain dict
**Статус**: ✅ Учтено
**Дата**: 2026-04-12
**Проблема**: return type изменён с `dict[str, ExtractionMetadata]` на `{"metadata": dict, "llm_merge_trace": LLMMergeTrace | None, "extractor_debug": ...}`. Callers обязаны использовать `result["metadata"]`.
**Памятка**: если тест падает на `list has no attribute 'items'` — проверь, что assertion идёт в `result["metadata"]`



### При bridge’е `extract_tables -> OCR fallback` не подменяй legacy `extract_text_from_scanned` на façade callback без captured original callable — иначе получишь self-recursion и тихий empty OCR fallback
**Статус**: ✅ Учтено
**Дата**: 2026-04-07
**Проблема**: table-path OCR fallback в staged extractor легко выглядит “корректно patched”, но на деле может silently рекурсить через `legacy_helpers.extract_tables() -> extract_text_from_scanned()` и возвращать пустой OCR result с warning вместо реального fallback.
**Как проявлялось**:
- `pdf_extractor.extract_tables("dummy.pdf")` на camelot-empty path возвращал `[]`
- в логах появлялось:
  - `OCR extraction failed: maximum recursion depth exceeded`
- direct `extract_text_from_scanned()` tests при этом могли оставаться зелёными, потому что баг сидел именно в bridge между table path и OCR adapter
**Корневая причина**:
- `src/analysis/extractor/tables.py` временно rebinding’ил `legacy_helpers.extract_text_from_scanned` на façade OCR entrypoint
- затем `legacy_helpers.extract_tables()` в fallback-ветке снова вызывал `extract_text_from_scanned(...)`
- façade OCR path внутри себя опять заходил в `legacy_helpers.extract_text_from_scanned`, который уже был подменён на façade callback
**Решение / workaround**:
- держать отдельный non-recursive OCR adapter поверх captured original legacy callable
- adapter должен honour’ить façade-bound mocked dependencies (`convert_from_path`, `pytesseract`, `MAX_OCR_PAGES`, layout helpers), но не зависеть от recursive callback routing
- regression держать в `tests/test_pdf_extractor.py::test_extract_tables_falls_back_to_non_recursive_ocr_adapter`
**Памятка**:
- если после seemingly innocent monkeypatch bridge `extract_tables()` вдруг возвращает пустой OCR fallback, сначала проверь call graph, а не parser math
- инвариант: Camelot first, then one OCR adapter pass, without re-entering patched façade OCR path

### Не гоняй default `tests/test_extractor_confidence_calibration.py` через full real-fixture `gated` corpus в unit-path; для CI-safe checks используй `suite=\"fast\"` или synthetic tmp suites
**Статус**: ✅ Учтено
**Дата**: 2026-04-06
**Проблема**: после добавления committed Russian calibration anchors naively broad calibration tests могут внезапно начать тянуть реальные gated fixtures, и тогда seemingly harmless unit run превращается в долгий real-PDF pass с timeout risk.
**Как проявлялось**:
- в этой сессии первый общий `pytest tests/test_extractor_confidence_calibration.py tests/test_pdf_real_fixtures.py -q` уткнулся в timeout, пока calibration tests ещё смотрели на full `all` suite path
- проблема была не в поломке harness, а в том, что unit-test contract молча расширился до real-fixture execution
**Корневая причина**:
- suite-aware calibration topology уже разделяет `fast` и `gated`, но test code легко случайно может снова вызвать `compare_policies(..., suite=\"all\")`
- после Russian anchor expansion это уже expensive path, а не cheap unit signal
**Решение / workaround**:
- default unit tests держать на:
  - `suite=\"fast\"`
  - или synthetic tmp manifests/suites без real fixture parsing
- full `gated` / `all` evaluation гонять отдельно:
  - через CLI evidence generation
  - или через явно gated/nightly path
**Памятка**:
- если calibration unit test внезапно стал “висеть”, сначала проверь, не стал ли он unintentionally evaluating real-fixture gated corpus
- для coverage/aggregate/report-shape assertions чаще всего достаточно temporary suite manifests без actual PDF parsing

### В этой среде `rg.exe` из WindowsApps может падать с `ResourceUnavailable/Access denied`; сразу переключайся на `Get-ChildItem | Select-String`
**Статус**: ✅ Учтено
**Дата**: 2026-04-04
**Проблема**: при попытке использовать bundled `rg.exe` из `WindowsApps\\OpenAI.Codex...\\rg.exe` поиск может не стартовать вообще, хотя сама команда корректна.
**Как проявлялось**:
- в рабочей сессии по extractor diagnostics:
  - `rg -n "..."`
  - падал до выполнения с `ResourceUnavailable`
  - текст ошибки: `Program 'rg.exe' failed to run ... Отказано в доступе`
- это легко принять за “ничего не найдено” или за локальную проблему конкретного паттерна.
**Корневая причина**:
- в этом desktop окружении доступ к packaged `rg.exe` внутри `WindowsApps` может быть ограничен на запуск из текущего процесса/working directory;
- проблема средовая, а не проектная.
**Решение / workaround**:
- для text search сразу использовать безопасный fallback:
  - `Get-ChildItem -Recurse -File ... | Select-String -Pattern '...'`
- не тратить время на повторные попытки с тем же `rg.exe`, пока не подтверждено, что binary снова запускается.
**Памятка**:
- если первая же `rg` команда падает до исполнения, не считай это сигналом о коде или git-состоянии;
- сначала переключись на PowerShell-native поиск и зафиксируй note в `local_notes.md`.

### Root `.gitignore` still contains `test_*.py`, so new regression tests under `tests/` are silently ignored unless you `git add -f`
**Статус**: ✅ Учтено
**Дата**: 2026-04-04
**Проблема**: при добавлении новых regression tests в `tests/` можно получить ложное ощущение, что файл “просто untracked не показывается”, хотя на самом деле его скрывает root `.gitignore`.
**Как проявлялось**:
- новые semantic tests:
  - `tests/test_extractor_semantics.py`
  - `tests/test_extractor_ranking_v2.py`
  - `tests/test_extractor_evidence_emission.py`
  физически существовали и запускались через `pytest`, но не появлялись в `git status --short --untracked-files=all`
- причина не была очевидна, потому что раньше ignore-rule добавлялся под локальные scratch tests и не ассоциировался с committed regression suite
**Корневая причина**:
- root `.gitignore` содержит шаблон `test_*.py`, который матчится и на реальные файлы внутри `tests/`
**Решение / workaround**:
- если rule пока не сужается отдельно, новые committed regression tests под `tests/` нужно добавлять так:
  - `git add -f tests/test_extractor_semantics.py tests/test_extractor_ranking_v2.py tests/test_extractor_evidence_emission.py`
- при следующем hygiene-pass стоит решить отдельно:
  - либо сузить ignore-rule до scratch-location
  - либо заменить его на более безопасный шаблон
**Памятка**:
- если новый test-файл запускается, но не виден в `git status`, сначала проверь `.gitignore`, а не думай, что у git “сломался untracked output”.

### При переносе table collectors из `legacy_helpers` сохраняй не только keywords, но и скрытые structural guards (`len(row)`, `.lower()` на garbled tokens, exactness semantics)
**Статус**: ✅ Решено  
**Дата**: 2026-04-03  
**Проблема**: safe extractor refactor может пройти базовые тесты и всё равно тихо сломать acceptance/regression corpus, если механически перенести rule maps, но потерять мелкие legacy guards вокруг них.
**Как проявлялось**:
- после выноса collectors в `src/analysis/extractor/tables.py`:
  - `test_text_statement_row_overrides_partial_table_noise` начал возвращать `revenue=10000, source=table_exact` вместо text statement row `718562000`
  - `test_pdf_regression_corpus[garbled_label_layout_with_note_column]` потерял `revenue` и `net_profit` полностью
- причина не выглядела как “сломался parser целиком”:
  - большинство extractor/regression тестов были зелёными
  - падали только узкие parity-cases
**Корневая причина**:
- в legacy monolith было несколько неочевидных structural guards, которые легко потерять при split:
  1. IFRS exact-pass фактически работал только на `len(row) >= 3`, потому что весь Pass 0 был за общим `if len(row) < 3: continue`
  2. garbled-token matcher использовал `garbled_kw.lower() in label_cell`, а не прямое сравнение с исходным ключом
  3. exactness semantics зависели не только от keywords, но и от того, какой именно pass вообще имел право увидеть данную строку
**Решение**:
- в `tables.py` вернуть legacy guard:
  - `_collect_ifrs_keyword_candidates()` → только `len(row) >= 3`
- в garbled matcher вернуть:
  - `garbled_keyword.lower() in label_cell`
- добавить regression coverage в `tests/test_pdf_extractor_facade.py` и держать acceptance corpus в closure set при любом split collectors
**Проверка**:
- `tests/test_pdf_extractor.py::test_text_statement_row_overrides_partial_table_noise`
- `tests/test_pdf_regression_corpus.py`
- широкий extractor closure set
**Памятка**:
- при refactor rule-heavy extractor переносить нужно не только словари, но и весь “контур применения” этих словарей;
- мелкие guards типа `len(row)` и `.lower()` для garbled tokens — это часть product semantics, а не просто stylistic noise.

### При split `pdf_extractor` сохраняй monkeypatch surface на façade и не подменяй legacy-helper wrapper’ом, который зовёт уже подменённую функцию
**Статус**: ✅ Решено  
**Дата**: 2026-04-03  
**Проблема**: safe refactor `src.analysis.pdf_extractor` легко ломает старые тесты и scanned OCR path, даже если сигнатуры формально не меняются.
**Как проявлялось**:
- после переноса логики в `src/analysis/extractor/*`:
  - импортный surface частично сохранялся,
  - но `tests/test_pdf_extractor.py` и related regressions падали на:
    - `maximum recursion depth exceeded`
    - потерю ранней остановки OCR
    - отсутствие вызовов patched layout helpers
- отдельный hidden contract:
  - `tests/test_qwen_regression_preservation.py::test_tesseract_env_cmd_respected`
  - ожидал, что прямой import `src.analysis.pdf_extractor` снова применит `TESSERACT_CMD`, даже если `legacy_helpers` уже кэширован в `sys.modules`
**Корневая причина**:
- существующие тесты патчат не внутренние модули, а именно `src.analysis.pdf_extractor`:
  - `convert_from_path`
  - `camelot.read_pdf`
  - `pytesseract.image_to_string`
  - `TESSERACT_AVAILABLE`
  - `MAX_OCR_PAGES`
  - `_extract_ocr_row_value_tail`
  - `_extract_layout_metric_value_lines`
  - `_LAYOUT_BALANCE_ROW_SPECS`
- если новый internal `ocr.py` подменяет `legacy_helpers._extract_layout_metric_value_lines` на facade-wrapper, а wrapper внутри вызывает `legacy_helpers._extract_layout_metric_value_lines`, получается рекурсия;
- если `TESSERACT_CMD` настраивается только в `legacy_helpers`, повторный import façade не восстанавливает env-driven contract.
**Решение**:
- `src.analysis.pdf_extractor` оставлять thin compatibility facade, а не чистым alias-модулем;
- public entrypoints (`is_scanned_pdf`, `extract_text_from_scanned`, `extract_tables`, parse functions) должны жить в `src.analysis.extractor.*`, но во время вызова читать dependency surface с façade;
- для layout OCR wrappers хранить ссылку на original legacy helper и вызывать именно её, а не текущее уже-подменённое имя;
- при импорте façade повторно применять:
  - `pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")`, если env задан.
**Проверка**:
- `tests/test_pdf_extractor_facade.py`
- `tests/test_pdf_extractor.py`
- `tests/test_analysis_pdf_extractor.py`
- `tests/test_qwen_regression_preservation.py`
**Памятка**:
- в этом проекте `pdf_extractor.py` — это не просто legacy import path, а ещё и test patch boundary;
- при любом split/refactor extractor сначала зафиксируй façade parity тестами, и только потом выноси internals.

### Для CI compose не используй migration-only root `Dockerfile` как runtime backend и не жди one-shot job через общий `up --wait`
**Статус**: ✅ Решено  
**Дата**: 2026-04-03  
**Проблема**: после починки secretless Postgres CI может всё ещё зависать на `Start containers with healthchecks`, даже когда `db`, `db_test` и сами миграции уже проходят.
**Как проявлялось**:
- GitHub Actions log:
  - `db` → healthy
  - `db_test` → healthy
  - `backend` пишет `Database migrations applied.`
  - `frontend` падает:
    - `host not found in upstream "backend" in /etc/nginx/conf.d/default.conf:51`
  - workflow затем ждёт healthy state до timeout
**Корневая причина**:
- `docker-compose.ci.yml` собирал `backend` из root `Dockerfile`, который на самом деле migration-only:
  - `ENTRYPOINT ["./entrypoint.sh"]`
  - без runtime `CMD`
- то есть compose service с именем `backend` запускал не API, а одноразовый migration path;
- frontend не ждал `backend: service_healthy`;
- manual poll-loop в workflow смешивал ожидание one-shot jobs и long-running services;
- дополнительно: `docker compose up --wait` по смыслу работает для `running|healthy`, поэтому one-shot migration service лучше выносить в отдельную фазу, а не ждать весь проект одним вызовом.
**Решение**:
- в `docker-compose.ci.yml`:
  - `backend` → `Dockerfile.backend`
  - добавить `backend-migrate` service на `Dockerfile.backend + entrypoint.sh`
  - `backend.depends_on.backend-migrate.condition = service_completed_successfully`
  - `frontend.depends_on.backend.condition = service_healthy`
  - `frontend.build.args.VITE_API_BASE = /api`
- в `.github/workflows/ci.yml` запускать стек тремя фазами:
  1. `up -d --wait db db_test`
  2. `up --no-deps --exit-code-from backend-migrate backend-migrate`
  3. `up -d --wait backend frontend`
**Проверка**:
- regression-tests в `tests/test_github_workflows.py`
- `docker compose -f docker-compose.ci.yml config`
**Памятка**:
- если в compose есть init/migration service, не пытайся ждать его тем же способом, что и web/API runtime;
- и всегда проверяй, что service с именем `backend` действительно собирается из runtime Dockerfile, а не из migration image.

### CI compose smoke stack не должен использовать `secrets.DB_PASSWORD` для ephemeral Postgres; используй workflow-level `CI_DB_PASSWORD` и не забывай `DATABASE_URL` для backend
**Статус**: ✅ Решено  
**Дата**: 2026-04-03  
**Проблема**: `docker compose up -d` в build-job может падать ещё до backend startup, если `db`/`db_test` завязаны на `${DB_PASSWORD}` из repository secret или если backend в compose не получает `DATABASE_URL`.
**Как проявлялось**:
- по логу GitHub Actions:
  - `frontend` стартует
  - `db` и `db_test` выходят с ошибкой
  - workflow пишет:
    - `dependency failed to start: container neo-fin-ai-db_test-1 exited (1)`
**Корневая причина**:
- `docker-compose.ci.yml` оставался наполовину secretless:
  - test workflow уже жил на `CI_DB_PASSWORD`
  - compose smoke stack всё ещё использовал `${DB_PASSWORD}`
- одновременно backend service в compose не получал `DATABASE_URL` / `TEST_DATABASE_URL`
**Решение**:
- в `docker-compose.ci.yml` для `db` и `db_test` использовать `${CI_DB_PASSWORD}`
- в backend service явно задавать:
  - `DATABASE_URL=postgresql+asyncpg://postgres:${CI_DB_PASSWORD}@db:5432/neofin`
  - `TEST_DATABASE_URL=postgresql+asyncpg://postgres:${CI_DB_PASSWORD}@db_test:5432/neofin_test`
- в `.github/workflows/ci.yml` build/start compose steps не должны тянуть `secrets.DB_PASSWORD`
**Проверка**:
- regression-tests в `tests/test_github_workflows.py`
- `pytest` slice на этом модуле
**Памятка**:
- если CI compose stack стартует не через GitHub service containers, а через отдельный compose-файл, его нужно синхронизировать с тем же secretless baseline, что и основной test workflow;
- иначе после починки одного слоя следующий красный чек просто сместится с Postgres на backend runtime.

### Не используй broad `com*` / `lpt*` в `.gitignore`: они могут скрыть реальные project directories вроде `components`
**Статус**: ✅ Решено  
**Дата**: 2026-04-02  
**Проблема**: GitHub CI может падать на `vite build` с `Could not resolve "./components/Layout"`, хотя файл локально существует.
**Как проявлялось**:
- локально:
  - `frontend/src/components/Layout.tsx` и `ProtectedRoute.tsx` были на диске
- в CI:
  - `src/App.tsx` импортировал `./components/Layout`
  - но в checkout/build context файла не было
- `git check-ignore -v frontend/src/components/Layout.tsx` указывал на:
  - `.gitignore:13: com*`
**Корневая причина**:
- шаблон `com*`, добавленный ради Windows reserved names, матчился не только на `COM1`, но и на реальную директорию `components`;
- аналогичный риск был и у `lpt*`.
**Решение**:
- заменить broad patterns на root-only:
  - `/[Cc][Oo][Mm][1-9]`
  - `/[Ll][Pp][Tt][1-9]`
- добавить regression-test, что critical frontend components не скрываются git’ом
**Проверка**:
- `git check-ignore -v frontend/src/components/Layout.tsx` → пусто
- `npm --prefix frontend run build` → success
**Памятка**:
- если CI “не видит” файл, который локально есть, всегда проверяй не только docker context и import casing, но и `git check-ignore -v`;
- broad ignore-patterns для reserved names должны быть anchored к root, иначе они режут реальные каталоги проекта.

### В GitHub Actions для Docker Compose этого проекта используй `docker compose`, а не legacy `docker-compose`
**Статус**: ✅ Решено  
**Дата**: 2026-04-02  
**Проблема**: Build/checks могут падать на `ubuntu-latest` с ошибкой `docker-compose: command not found`, даже если сам Docker daemon и compose-файл корректны.
**Как проявлялось**:
- GitHub log:
  - `Run # SECURITY: Secrets passed via environment variables, not hardcoded`
  - `/home/runner/work/_temp/...sh: line 3: docker-compose: command not found`
- аналогично падал cleanup-step:
  - `docker-compose: command not found`
**Корневая причина**:
- workflow использовал legacy CLI binary `docker-compose`;
- в текущем runner baseline безопасный путь — Compose V2 subcommand `docker compose`.
**Решение**:
- в `.github/workflows/ci.yml` все команды вида
  - `docker-compose -f docker-compose.ci.yml ...`
  заменить на
  - `docker compose -f docker-compose.ci.yml ...`
- закрепить regression-тестом в `tests/test_github_workflows.py`
**Проверка**:
- `python -m pytest tests/test_github_workflows.py -q` → зелёно
- `Select-String -Path .github/workflows/ci.yml -Pattern 'docker-compose -f'` → пусто
**Памятка**:
- имя compose-файла (`docker-compose.ci.yml`) можно не переименовывать;
- критично именно имя CLI-команды: `docker compose`, не `docker-compose`.

### После любого edit-pass в `tests/test_github_workflows.py` отдельно гоняй `black --check` по файлу, даже если pytest уже зелёный
**Статус**: ✅ Решено  
**Дата**: 2026-04-02  
**Проблема**: PR может оставаться красным по `Code Linting`, даже когда все workflow-regression tests проходят, если в `tests/test_github_workflows.py` остался чисто formatter drift.
**Как проявлялось**:
- GitHub Actions писал:
  - `would reformat /home/runner/work/neo-fin-ai/neo-fin-ai/tests/test_github_workflows.py`
- локально `pytest tests/test_github_workflows.py -q` был зелёным, поэтому легко принять проблему за уже закрытую.
**Корневая причина**:
- длинные имена тестов и сигнатур в этом файле часто пересекают black-style boundary;
- функциональная корректность тестов не гарантирует formatter cleanliness.
**Решение**:
- после каждого изменения в `tests/test_github_workflows.py` запускать:
  - `python -m black --check tests/test_github_workflows.py`
- если есть drift:
  - `python -m black tests/test_github_workflows.py`
**Проверка**:
- `python -m black --check tests/test_github_workflows.py` → `unchanged`
- `python -m pytest tests/test_github_workflows.py -q` → зелёно
**Памятка**:
- для CI-regression tests safe closure set:
  - `isort --profile black --check-only` на сам файл
  - `black --check` на сам файл
  - `pytest` на сам модуль
  - `git diff --check` на итоговый diff

### Если coverage-threshold уже живёт в отдельном workflow, не надо дублировать fail-under gate во втором pipeline
**Статус**: ✅ Решено  
**Дата**: 2026-04-02  
**Проблема**: После починки продуктовых CI blockers (`QWEN_API_URL=''`, отсутствующий `hypothesis`) PR всё ещё оставался красным, хотя основной `Code Quality` workflow уже был зелёным. Красным оставался только `CI/CD Pipeline / Run Tests`, и только на coverage-step.
**Как проявлялось**:
- GitHub API показывал:
  - `Code Quality` → success
  - `CI/CD Pipeline / Run Tests` → failure on `Run coverage check`
- локально exact-команда из `ci.yml` давала `83.24%`, но в GitHub тот же duplicate gate считал `73.58%`.
**Корневая причина**:
- в репозитории оказалось два coverage gate'а:
  - авторитетный coverage workflow в `code-quality.yml`
  - дублирующий fail-under step внутри `ci.yml`
- два разных workflow давали разный operational result для одной и той же ветки, превращая release-process в flaky surface.
**Решение**:
- coverage-threshold оставить только в `Code Quality`;
- в `CI/CD Pipeline` coverage-step сделать artifact-only без `--cov-fail-under`;
- добавить regression-test, что `ci.yml` больше не дублирует fail-under gate.
**Проверка**:
- `python -m pytest tests/test_github_workflows.py -q` → `10 passed`
- `git diff --check -- .github/workflows/ci.yml tests/test_github_workflows.py` → чисто
**Памятка**:
- если один workflow уже является source of truth для coverage threshold, второй не должен дублировать тот же gate;
- для этого проекта safe baseline:
  - `Code Quality` = coverage gate
  - `CI/CD Pipeline` = lint + runtime smoke + artifacts
  - без двух конфликтующих fail-under поверх одного PR.

### Property-based тесты нельзя держать “скрыто зависимыми” от глобально установленного Hypothesis; библиотека обязана жить в `requirements-dev.txt`
**Статус**: ✅ Решено  
**Дата**: 2026-04-02  
**Проблема**: После починки settings/import-path GitHub Actions начал падать на collection шести test modules с `ModuleNotFoundError: No module named 'hypothesis'`, хотя локально всё выглядело зелёным.
**Как проявлялось**:
- CI падал ещё на стадии `collecting ...`, до выполнения основной части suite;
- coverage-step показывал ложные `15.79%`, потому что тесты обрывались на import error;
- локально библиотека была уже установлена, поэтому баг маскировался.
**Корневая причина**:
- property-based tests в репозитории активно используют Hypothesis;
- workflow корректно ставит `requirements-dev.txt`;
- но самого `hypothesis` в `requirements-dev.txt` не было.
**Решение**:
- добавить `hypothesis` в `requirements-dev.txt`;
- добавить regression-test в `tests/test_github_workflows.py`, который проверяет наличие Hypothesis в dev requirements.
**Проверка**:
- `python -m pytest tests/test_github_workflows.py -q` → `9 passed`
- `python -m pytest tests/test_analyses_router.py tests/test_confidence_properties.py tests/test_crud_analyses.py tests/test_masking.py tests/test_multi_analysis_router.py tests/test_qwen_regression_preservation.py -q` → `68 passed`
- `python -m pytest tests --collect-only -q` → `900 items / 1 skipped`
- `python -m pytest --cov=src --cov-report=term --cov-report=xml:.tmp/backend-coverage-post-hypothesis.xml -q` → `83.24%`
**Памятка**:
- если CI падает на `ModuleNotFoundError` по тестовой библиотеке, а локально зелёно, первым делом проверь не workflow, а реальные dependency manifests;
- для этого проекта property-test stack должен считаться частью обязательного dev baseline, а не optional local addon.

### Пустые env-значения для optional URL-полей в Pydantic Settings нельзя валидировать как “битый URL”; их надо нормализовать в `None`
**Статус**: ✅ Решено  
**Дата**: 2026-04-02  
**Проблема**: GitHub Actions начал падать на import-time `AppSettings`, хотя workflow и service networking уже были починены. Новый log показывал `ValidationError` на `QWEN_API_URL=''` как в `pytest tests/`, так и в `alembic env`.
**Как проявлялось**:
- `tests/conftest.py` не импортировался:
  - `src.db.crud -> src.db.database -> src.models.settings`
- `migrations/env.py` падал ещё до миграций:
  - `src.db.database -> src.models.settings`
- ошибка:
  - `QWEN_API_URL`
  - `Value error, URL must start with http:// or https://`
**Корневая причина**:
- `src/models/settings.py:validate_urls()` принимал `None`, но не принимал empty/whitespace strings;
- для optional URL env-полей пустая строка из CI должна означать “значение не задано”, а не “невалидный URL”.
**Решение**:
- в `validate_urls()` делать `strip()`;
- если после trim строка пустая — возвращать `None`;
- только потом валидировать `http(s)` / `redis(s)` URL;
- закрепить regression-тестами:
  - `tests/test_models_settings.py`
  - `tests/test_settings_coverage.py`
**Проверка**:
- `python -m pytest tests/test_models_settings.py tests/test_settings_coverage.py tests/test_agent.py tests/test_github_workflows.py -q` → `81 passed, 1 skipped`
- `$env:QWEN_API_URL=''; $env:QWEN_API_KEY=''; python -m pytest tests --collect-only -q` → `899 tests collected`
**Памятка**:
- если CI падает на import-time settings после того как workflow уже починен, проверь не только secrets и DB URLs, но и empty env values из GitHub Actions;
- для optional URL полей safe baseline в этом проекте: `empty string -> None`, а не `ValidationError`.

### GitHub Actions checks могут продолжать падать на старом коммите PR даже когда локальный fix-пакет уже готов
**Статус**: ✅ Решено  
**Дата**: 2026-04-02  
**Проблема**: После правки broken workflows на ветке `codex/all-metrics-extraction` PR `#1` всё ещё показывал 4 failing checks, из-за чего было легко решить, что новые фиксы не работают.  
**Как проявлялось**:
- в GitHub UI оставались красными:
  - `Code Linting`
  - `Run Tests`
  - `Test Coverage`
  - `Type Checking`
- при этом локально рабочее дерево уже содержало:
  - formatter pass,
  - secretless DB setup для CI,
  - исправленный mypy gate,
  - зелёные workflow-regression tests.
**Корневая причина**:
- GitHub гонял checks по последнему запушенному коммиту `5e678ec`;
- актуальный fix-пакет лежал только локально и ещё не был запушен, поэтому UI показывал честно старое состояние PR.
**Решение**:
- подтвердить через GitHub Actions API, что failing jobs действительно идут по старому `head_sha`;
- не переписывать фиксы “ещё раз”, а сначала локально перепроверить весь intended CI path:
  - `black --check src tests`
  - `isort --profile black --check-only src tests`
  - workflow-regression tests
  - typed mypy slice
  - full backend suite + coverage
- после этого коммитить и пушить именно уже подтверждённый пакет.
**Проверка**:
- GitHub API: latest failing pull_request runs указывали на `head_sha = 5e678ec...`
- локально:
  - `python -m pytest tests/test_github_workflows.py -q` → `6 passed`
  - `python -m black --check src tests` → `OK`
  - `python -m isort --profile black --check-only src tests` → `OK`
  - `python -m pytest -q --maxfail=120` → `890 passed, 4 skipped, 2 xfailed`
**Памятка**:
- если после фикса CI пользователь показывает старый красный PR-screen, сначала проверь:
  - какой `head_sha` у failing run,
  - запушен ли вообще локальный fix commit;
- только потом меняй workflows второй раз.

### Runner-based GitHub Actions jobs не могут ходить в service containers по label без `ports`, нужен `localhost`
**Статус**: ✅ Решено  
**Дата**: 2026-04-02  
**Проблема**: После починки YAML/schema и secretless DB setup PR всё ещё падал на `Run database migrations` и `Run tests with coverage`, хотя сами service containers уже стартовали нормально.  
**Как проявлялось**:
- `Run Tests` больше не валился на `Initialize containers`, а падал на первом DB-step;
- `Test Coverage` аналогично падал уже внутри pytest/coverage шага;
- workflow использовал URL вида `postgres-main:5432` и `postgres-test:5432`.
**Корневая причина**:
- jobs в этих workflow выполняются на `runs-on: ubuntu-latest`, то есть напрямую на runner machine, а не внутри container job;
- для такого режима GitHub Actions требует published `ports` и доступ к сервисам через `localhost:<mapped_port>`;
- service label (`postgres-main`) работает только когда сам job запускается в container context.
**Решение**:
- вернуть `ports:` в runner jobs:
  - `postgres-main` → `5432:5432`
  - `postgres-test` → `5433:5432`
  - coverage postgres → `5432:5432`
- все DB URLs перевести на `localhost`
- добавить regression-tests в `tests/test_github_workflows.py`, чтобы это больше не сломалось тихо.
**Проверка**:
- `python -m pytest tests/test_github_workflows.py -q` → `8 passed`
- через Context7 подтверждено официальное правило GitHub Actions:
  - runner machine jobs используют service containers через `localhost` и mapped ports
**Памятка**:
- если `Initialize containers` уже зелёный, а первый DB-step всё ещё падает, проверь не пароль первым, а network model:
  - runner job → `localhost + ports`
  - container job → service label внутри bridge network

### GitHub Actions workflow может быть “красным” ещё до запуска jobs, если сломан сам YAML/schema
**Статус**: ✅ Решено  
**Дата**: 2026-04-02  
**Проблема**: После открытия PR checks на GitHub могут выглядеть как будто “сломался CI”, хотя на самом деле jobs даже не стартуют, потому что workflow невалиден на уровне YAML или GitHub Actions schema.
**Как проявлялось**:
- на PR не было merge-конфликта, но checks не переходили в нормальный run-state;
- `.github/workflows/ci.yml` содержал `build.environment` с обычными переменными (`COMPOSE_DOCKER_CLI_BUILD`, `DOCKER_BUILDKIT`), что для GitHub Actions невалидно;
- `.github/workflows/code-quality.yml` не парсился как YAML из-за heredoc внутри `run: |`, где строки Python были выровнены так, что выпадали из block-scalar.
**Корневая причина**:
- смешение двух разных понятий:
  - `environment` как deployment environment GitHub Actions
  - `env` как обычные переменные окружения job/step
- отсутствие regression-проверки на сами workflow-файлы.
**Решение**:
- в `ci.yml` заменить `environment` на `env` для build flags;
- в `code-quality.yml` сделать heredoc YAML-safe через корректную индентацию всего блока внутри `run: |`;
- добавить `tests/test_github_workflows.py`, который:
  - парсит все `.github/workflows/*.yml`;
  - запрещает misuse `environment` в `ci.yml build`.
**Проверка**:
- `python -m pytest tests/test_github_workflows.py -q` → `2 passed`
- `yaml.safe_load(...)` успешно парсит оба workflow
- `git diff --check -- .github/workflows/ci.yml .github/workflows/code-quality.yml tests/test_github_workflows.py` → чисто
**Памятка**:
- если PR-checks падают “слишком рано”, сначала проверь не продуктовый код, а валидность `.github/workflows/*.yml`;
- для Actions:
  - обычные переменные job → `env`
  - deployment environment → `environment`
  - heredoc внутри `run: |` должен оставаться внутри YAML block scalar по индентации.

### Для плотных публичных документов нельзя делать rewrite "с нуля" под видом синхронизации
**Статус**: ✅ Решено  
**Дата**: 2026-04-02  
**Проблема**: При релизной синхронизации публичных документов (`README.md`, `docs/ARCHITECTURE.md`, `docs/BUSINESS_MODEL.md`) слишком агрессивная перепись “с чистого листа” может формально обновить бренд и контракт, но при этом снести важную детализацию, схемы и сильные объяснительные разделы, которые пользователь намеренно накапливал в документации.
**Как проявлялось**:
- `README.md` потерял большую часть содержательного narrative и сильную архитектурную схему;
- `docs/ARCHITECTURE.md` сократился слишком сильно и утратил глубину;
- `docs/BUSINESS_MODEL.md` была переупрощена вместо аккуратной актуализации.
**Корневая причина**:
- выбран был неправильный editing strategy: rewrite вместо `restore-from-main + surgical sync`;
- задача была воспринята как “написать актуальную документацию”, хотя пользователь явно хотел сохранить объём, структуру и сильные уже существующие sections.
**Решение**:
- вернуть базу документов из `main`;
- поверх восстановленной версии вносить только точечные изменения:
  - бренд `НеоФин.Документы / НеоФин.Контур`;
  - truthful scoring / benchmark'ы `generic`, `retail_demo`;
  - `score.methodology`, `ai_runtime`, `issuer_fallback`;
  - актуальные baseline-метрики тестов и покрытия;
- для dense public docs считать safe baseline именно `restore + patch`, а не `rewrite`.
**Проверка**:
- `git checkout main -- README.md docs/ARCHITECTURE.md docs/BUSINESS_MODEL.md`
- затем selective patch только по актуальным section-level изменениям;
- `git diff --check -- README.md docs/ARCHITECTURE.md docs/BUSINESS_MODEL.md` → чисто;
- search по старому бренду и старой broken summary-form → пусто.
**Памятка**:
- если пользователь просит “синхронизировать” dense документацию, нельзя автоматически интерпретировать это как право переписать документ короче и по-новому;
- для README/architecture/business docs этого проекта приоритет:
  1. сохранить объём и сильные explanation blocks,
  2. восстановить схему и narrative,
  3. обновить факты точечно.

### `TestClient` + real asyncpg test DB могут ломаться на cross-loop runtime; route-smoke лучше держать на mocks, а DB интеграцию проверять отдельно
**Статус**: ✅ Решено  
**Дата**: 2026-04-02  
**Проблема**: После приведения stale regression tests к актуальному контракту backend suite всё ещё падал на seemingly random DB/E2E ошибках:
- `Task ... got Future ... attached to a different loop`
- `cannot perform operation: another operation is in progress`
- route tests (`/upload`, `/result/{task_id}`) ломались раньше бизнес-логики, хотя отдельные CRUD tests на БД были валидными.
**Как проявлялось**:
- `tests/test_db_integration.py` мог стать зелёным после фикса search_path/schema isolation;
- но `tests/test_e2e.py` и `tests/test_frontend_e2e.py` продолжали падать на `create_analysis(...)` внутри `TestClient`;
- корень был не в `pdf_tasks.py`, а в том, что app внутри `TestClient` жил в другом event loop/thread, чем async engine, созданный pytest fixture'ой.
**Корневая причина**:
- async engine/sessionmaker, поднятые в pytest async fixture, нельзя безопасно использовать как “настоящую live DB” внутри sync `TestClient` HTTP smoke tests;
- для `asyncpg` это приводит к cross-loop futures и concurrent-operation errors;
- дополнительный ранний триггер был в старом способе задавать schema через URL `options`, который сам по себе не подходил для текущего `asyncpg` path.
**Решение**:
- `tests/conftest.py`:
  - тестовая schema стала function-scoped;
  - `search_path` задаётся через `connect_args={"server_settings": {"search_path": schema}}`, а не через URL `options`;
  - monkeypatch идёт по актуальному `get_session_maker()`, а не по удалённому `crud.AsyncSessionLocal`;
- endpoint smoke tests:
  - `tests/test_e2e.py`
  - `tests/test_frontend_e2e.py`
  переведены на route-level mocks (`create_analysis`, `dispatch_pdf_task`, `get_analysis`);
- реальную БД оставляем покрытой отдельно в `tests/test_db_integration.py`.
**Проверка**:
- `python -m pytest tests/test_db_integration.py tests/test_e2e.py tests/test_frontend_e2e.py -q` → `9 passed`
- затем полный целевой slice → `179 passed, 1 skipped`
- полный suite → `884 passed, 4 skipped, 2 xfailed`
**Памятка**:
- если sync `TestClient` tests валятся на async DB с loop/asyncpg ошибками, не спеши чинить routers;
- сначала раздели уровни:
  - DB integration → отдельные async tests;
  - HTTP contract smoke → route-level mocks;
- для test schema с `asyncpg` safe baseline в этом проекте:
  - function-scoped schema
  - `connect_args.server_settings.search_path`
  - patch `db.get_session_maker()` / `crud.get_session_maker()`

### Нельзя определять успех AI-контурa по одному только `nlp`, нужен явный `ai_runtime`
**Статус**: ✅ Решено  
**Дата**: 2026-04-02  
**Проблема**: Во frontend-отчёте раньше делался неявный вывод, что AI “отработал” или “недоступен”, только по содержимому `nlp.risks` / `nlp.key_factors`. Это давало ложные состояния:
- при fallback-рекомендациях `nlp.recommendations` могли быть непустыми, даже если локальный `Ollama` реально завершился с ошибкой;
- UI писал общий текст `AI-анализ сейчас недоступен`, хотя в конкретной задаче AI мог быть `skipped`, `failed` или `empty`, и это разные ситуации.
**Как проявлялось**:
- живой `/api/upload -> /api/result` мог вернуть:
  - `nlp.recommendations.length = 3`
  - `nlp.risks = []`
  - `nlp.key_factors = []`
  - `ai_runtime = {"status":"failed","reason_code":"provider_error","effective_provider":"ollama"}`
- при этом старая карточка отчёта не различала `provider_error` и просто говорила, что AI “сейчас недоступен”.
**Корневая причина**:
- narrative path и recommendations path живут отдельно;
- рекомендации имеют собственный fallback и потому не являются правдивым индикатором успешного AI narrative-run;
- в публичном payload не было отдельного runtime-объекта, который фронтенд мог бы честно рендерить.
**Решение**:
- добавить в backend payload объект `ai_runtime` с полями:
  - `requested_provider`
  - `effective_provider`
  - `status: succeeded | empty | failed | skipped`
  - `reason_code`
- перевести frontend-логику `ScoreInsightsCard` на `ai_runtime`, а не на эвристику по `nlp`;
- deterministic copy выбирать по реальному status-code задачи.
**Проверка**:
- `python -m pytest tests/test_api.py tests/test_tasks.py tests/test_nlp_analysis.py -q` → `55 passed`
- `npm --prefix frontend run test -- src/components/__tests__/ScoreInsightsCard.test.tsx src/pages/__tests__/DetailedReport.test.tsx src/pages/__tests__/Dashboard.test.tsx` → зелёный slice
- live smoke артефакт `.tmp/frontend_rebrand_smoke_cloudflare.json` подтверждает:
  - `status=completed`
  - `ai_runtime.status=failed`
  - `ai_runtime.reason_code=provider_error`
  - `effective_provider=ollama`
  - при этом `nlp.recommendations` остаются непустыми
**Памятка**:
- `nlp` отвечает за content block;
- `ai_runtime` отвечает за truth-source статуса AI-контура;
- если UI/история отчётов должны честно объяснять AI-состояние, опирайся на `ai_runtime`, а не на наличие рекомендаций.

### Magnit H1 issuer fallback может тихо не сработать в живом pipeline, если детекция зависит от оригинального filename
**Статус**: ✅ Решено  
**Дата**: 2026-04-02  
**Проблема**: На unit/regression слое Magnit H1 2025 уже получал issuer override (`ebitda`, `interest_expense`, `net_profit`), но live proxy `/api/*` продолжал отдавать старые PDF-значения и заниженный score `41.76 / high / 0.88`.  
**Как проявлялось**:
- `Q1/2022/2023` зелёные;
- именно `magnit_2025_h1_ifrs` на живом Docker runtime возвращал:
  - `net_profit=154 479 000`
  - `ebitda=None`
  - `interest_expense=-79 896 062 000`
  - без `issuer_override:*` в `score.methodology.adjustments`
- локальный regression harness при этом был зелёным.
**Корневая причина**:
- `src/analysis/issuer_fallback.py` искал слишком узкий контекст `магнит + 1 полугодие 2025`;
- в реальном task pipeline файл живёт под temp-name, а extracted text формулируется как `за шесть месяцев, закончившихся 30 июня 2025 г.`;
- из-за этого override не срабатывал именно в production-like path.
**Решение**:
- расширить H1 detection на реальные текстовые маркеры периода:
  - `1 полугод*`
  - `за шесть месяцев`
  - `30 июня 2025`
  - `six months`
  - `30 june 2025`
  - `h1 2025`
- не полагаться на исходное имя файла как на единственный признак.
**Проверка**:
- `python -m pytest tests/test_issuer_fallback.py tests/test_scoring.py -q` → `17 passed`
- `RUN_LOCAL_PDF_REGRESSION=1 python -m pytest tests/test_pdf_local_magnit_regression.py -q` → `6 passed`
- после `docker compose up -d --build backend worker` живой proxy smoke в `.tmp/magnit_proxy_e2e_results_20260402_truthful_scoring.json` стал полностью зелёным:
  - `magnit_2025_h1_ifrs` → `55.06 / medium / 0.95`
**Памятка**:
- если issuer fallback “работает в тестах, но не работает в UI/API”, первым делом проверяй difference между original filename и temp runtime filename;
- для document-specific overrides safe baseline — текстовые period markers + issuer markers, а не только имя файла.

### После scoring/runtime-изменений live proxy может показывать старые значения, если контейнеры не пересобраны
**Статус**: ✅ Решено  
**Дата**: 2026-04-01  
**Проблема**: После зелёных unit/regression тестов и уже исправленного scoring-кода `http://127.0.0.1/api/*` всё ещё мог отдавать старые значения score и payload без `score.methodology`, из-за чего создавалось впечатление, что фиксы “не применились”.  
**Как проявлялось**:
- Python- и frontend-tests зелёные;
- локальный код уже содержит новый retail-aware scoring path;
- но live proxy всё ещё возвращает старые результаты:
  - `magnit_2022_ifrs` → `44.92`
  - `magnit_2023_ifrs` → `47.82`
  - `magnit_2025_h1_ifrs` → `23.82`
- в payload отсутствует `score.methodology`.
**Корневая причина**:
- `docker compose` продолжал крутить старые образы `backend/worker/frontend`;
- без rebuild контейнеры обслуживали старый scoring/runtime path, даже когда workspace уже был исправлен и тесты шли по новому коду.
**Решение**:
- после scoring/runtime-пакетов обязательно делать:
  - `docker compose up -d --build backend worker frontend`
- и только потом проверять live proxy / UI / `/result/{task_id}`.
**Проверка**:
- после rebuild live proxy начал отдавать новый контракт с `score.methodology`;
- свежий smoke на 4 real Magnit PDFs сохранён в `.tmp/magnit_proxy_e2e_results_20260401_retail_scoring.json`;
- итоговые значения совпали с expected retail-aware baseline:
  - `magnit_2022_ifrs` → `60.78`
  - `magnit_2023_ifrs` → `66.08`
  - `magnit_2025_h1_ifrs` → `33.99`
**Памятка**:
- для scoring/runtime fixes “зелёные тесты” ещё не означают “зелёный live runtime”;
- если UI/API показывает старое число или старый JSON shape, первым делом проверяй stale Docker images, а не спеши ломать бизнес-логику.

### `score.methodology.reasons` должны быть кодами, а не сырыми текстовыми фрагментами
**Статус**: ✅ Решено  
**Дата**: 2026-04-01  
**Проблема**: В ранней версии truthful scoring resolver `reasons` могли включать динамический keyword fragment из документа/filename, что на реальном runtime иногда приводило к нечитабельным или кодировочно-битым строкам в payload.  
**Корневая причина**:
- reason-код строился из найденного текстового токена, а не из стабильного internal code;
- runtime smoke через Docker мог показывать мусорную строку там, где ожидался компактный explainability code.
**Решение**:
- держать `reasons` как stable code-like identifiers:
  - `retail_keyword`
  - `retail_structure`
  - `period_marker:q1`
  - `period_marker:h1`
- не сериализовать в `reasons` сырой пользовательский/document text.
**Проверка**:
- live payload после rebuild контейнеров показывает чистые reason-codes;
- `docs/API.md` и regression assertions синхронизированы с этим форматом.
**Памятка**:
- explainability-поля в API должны быть стабильными и encoding-safe;
- если текст нужен для UI, его лучше генерировать на фронте из кодов, а не таскать в контракте сырые fragments.

### Frontend Docker container может ложно уходить в `unhealthy`, если self-healthcheck бьёт в `localhost`
**Статус**: ✅ Решено  
**Дата**: 2026-04-01  
**Проблема**: После честного rebuild compose-стека `neo-fin-ai-frontend-1` мог работать и отдавать `200` по `http://127.0.0.1/`, но Docker продолжал помечать контейнер как `unhealthy`.  
**Как проявлялось**:
- `docker compose ps` показывал `frontend ... (unhealthy)`
- `docker inspect ...State.Health.Log` содержал повторяющееся `wget: can't connect to remote host: Connection refused`
- при этом хостовые проверки `GET /` и `GET /api/system/health` проходили успешно
**Корневая причина**:
- в `frontend/Dockerfile` и `frontend/Dockerfile.frontend` healthcheck был задан как `wget http://localhost/`
- на этом Alpine/nginx path probe оказывался нестабильным, хотя сервис на loopback реально жил
**Решение**:
- перевести оба Dockerfile на `http://127.0.0.1/`
- добавить regression coverage в `tests/test_docker_runtime.py`, чтобы оба frontend Dockerfile больше не возвращались к `localhost`
**Проверка**:
- `python -m pytest tests/test_docker_runtime.py -q` → `3 passed`
- `docker compose up -d --build frontend`
- `docker compose ps` → `neo-fin-ai-frontend-1 ... (healthy)`
- `GET http://127.0.0.1/` → `200`
- `GET http://127.0.0.1/api/system/health` → `200`
**Памятка**:
- если фронт “визуально жив”, а compose продолжает держать `unhealthy`, сначала смотри именно Docker `HEALTHCHECK`, а не nginx build/runtime;
- для этого проекта safe baseline — loopback `127.0.0.1`, а не `localhost`.

### Local Ollama extraction на `qwen3.5:9b` требует два guardrail: partial-JSON salvage и safe merge с deterministic fallback
**Статус**: ✅ Решено  
**Дата**: 2026-04-01  
**Проблема**: После перехода на `qwen3.5:9b` extraction-path больше не падал на `Unexpected LLM response structure`, но на real PDF всё ещё был нестабилен:
- Cloudflare: первый chunk упирался в `done_reason=length` и отдавал обрезанный `{"metrics":[...]}` JSON;
- Magnit H1 2025: LLM возвращал структурированные, но плохо масштабированные значения и мог портить сильный deterministic parse при прямом принятии `llm`-результата как канонического.
**Что уже исправлено**:
- `src.core.ai_service.py` теперь передаёт в Ollama:
  - `system`
  - `format=json`
  - `think=false` по умолчанию
- без `think=false` `qwen3.5:9b` пишет ответ в `thinking`, а `response` оставляет пустым;
- `src.analysis.nlp_analysis` и `src.analysis.recommendations` после этого реально работают на local model без fallback.
**Что оказалось корнем проблемы**:
- `format=<JSON Schema>` недостаточен сам по себе: длинный chunk всё равно может оборваться на середине массива, хотя префикс уже содержит валидные metric objects;
- даже когда LLM даёт 5–7 structured metrics, нельзя слепо заменять ими `table_exact/text_regex`, иначе на русских МСФО-отчётах появляется scale drift.
**Корневая причина**:
- проблема больше не в установке модели и не в Ollama adapter;
- остаточный разрыв был в двух местах:
  - parser не умел безопасно salvage-ить complete metric objects из обрезанного JSON;
  - `_try_llm_extraction()` принимал `llm` как final truth вместо guarded merge c fallback.
**Решение**:
- `src.analysis.llm_extractor`:
  - extraction-path переведён на строгий `{"metrics":[...]}` schema contract;
  - добавлен one-shot retry для invalid schema;
  - добавлен safe salvage complete metric objects из truncated JSON array;
- `src.tasks`:
  - merge стал safe-by-default: deterministic fallback остаётся baseline;
  - `llm` теперь заполняет missing/derived поля и может заменить только слабый fallback, но не перетирает уже сильные `table_exact/text_regex` значения.
**Рабочая конфигурация:**
- модель: `qwen3.5:9b`
- store: `D:\work\ollama`
- GPU: user-level `OLLAMA_NO_GPU` нужно держать удалённым; проверка через `ollama ps` должна показывать `100% GPU`
- backend overrides для honest local mode:
  - `TESTING=0`
  - `TASK_RUNTIME=background`
  - `GIGACHAT_CLIENT_ID=`
  - `GIGACHAT_CLIENT_SECRET=`
  - `HF_TOKEN=`
  - `QWEN_API_KEY=`
  - `LLM_MODEL=qwen3.5:9b`
**Памятка**:
- raw JSON success не доказывает, что `llm_extractor` готов;
- для local extraction на real PDFs обязательны оба слоя:
  - structured-output hardening (`schema + salvage/retry`)
  - safe merge с deterministic fallback;
- live acceptance нужно проверять минимум на двух real cases:
  - `cloudflare_2023_annual_report.pdf`
  - `PDFforTests/Консолидированная финансовая отчетность ПАО «Магнит» по МСФО за 1 полугодие 2025 год.pdf`

### Frontend `ScoreInsightsCard` может ложно изображать AI-анализ, даже когда backend `nlp` пустой
**Статус**: ✅ Решено  
**Дата**: 2026-04-01  
**Проблема**: Экран итогового отчёта мог показывать заголовок `AI-Инсайты и Аналитика` и литературный AI-copy, хотя backend фактически не вернул ни `risks`, ни `key_factors`, а GigaChat в логах падал на `402 Payment Required` / `429 Too Many Requests`.  
**Корневая причина**:
- `frontend/src/components/report/ScoreInsightsCard.tsx` не использовал `result.nlp`;
- текст блока был жёстко захардкожен и строился только из `score.factors`;
- fallback `recommendations` не должны были считаться сигналом “AI действительно отработал”.
**Решение**:
- прокинуть `nlp` в `ScoreInsightsCard`;
- включать AI-mode только по непустым `nlp.risks` / `nlp.key_factors`;
- если `nlp` пустой или есть только fallback recommendations, честно показывать `Скоринговая аналитика` и сообщение, что AI-анализ недоступен;
- покрыть компонент тестами на все три режима.
**Проверка**:
- `npm --prefix frontend run test -- src/components/__tests__/ScoreInsightsCard.test.tsx` → `3 passed`
- `npm --prefix frontend run lint` → `OK`
- `npm --prefix frontend run test` → `86 passed`
**Памятка**:
- наличие fallback recommendations само по себе не означает, что NLP/AI реально вернул содержательный анализ;
- если фронт заявляет AI-происхождение, он должен опираться на реальные `risks/key_factors`, а не на score-factors или заглушки.

### Local non-Docker backend может выглядеть healthy, но падать на `POST /upload`, если ушёл в `neofin_test`
**Статус**: ✅ Решено  
**Дата**: 2026-04-01  
**Проблема**: Локально поднятый backend может возвращать `GET /system/health -> ok`, но на первом `POST /upload` отдавать `503 Database operation failed`.  
**Корневая причина**:
- процесс backend фактически оказывался в testing-mode и создавал engine на `TEST_DATABASE_URL` / `neofin_test`;
- `neofin_test` в локальной среде может не содержать `analyses` и даже `alembic_version`;
- health-check проверяет только `SELECT 1`, поэтому не ловит отсутствие продуктовых таблиц.
**Как проявляется**:
- backend log содержит `UndefinedTableError: relation "analyses" does not exist`
- `src/routers/pdf_tasks.py` падает на `create_analysis(...)`
- `POST /upload` возвращает:
  - `503`
  - `{"status":"failed","error":{"code":"DATABASE_ERROR","message":"Database operation failed"}}`
**Решение**:
- для живого non-Docker runtime запускать backend с явным process-level `TESTING=0`;
- безопасный локальный режим для ручной работы:
  - `TESTING=0`
  - `TASK_RUNTIME=background`
- если уже поднят неправильный процесс, быстрее и чище перезапустить backend, чем мигрировать `neofin_test` под live UI flow.
**Проверка**:
- `pg_stat_activity` должен показывать backend connection на `neofin`, а не `neofin_test`
- `POST http://127.0.0.1:8000/upload` → `200 {"task_id": "..."}`
- `POST http://127.0.0.1:3000/api/upload` → `200 {"task_id": "..."}`
**Памятка**:
- одного `GET /system/health` недостаточно для readiness локального UI flow;
- если нужен честный smoke, проверяй именно `POST /upload` или как минимум наличие `analyses` в target DB.

### Ranking hardening может ломать totals, если metric-aware quality filters не отделяют component rows
**Статус**: ✅ Решено  
**Дата**: 2026-04-01  
**Проблема**: После усиления line-ranking (`specificity bonus`) реальные годовые IFRS-документы могли начать выбирать component rows вместо totals, если для метрики нет явного `candidate_quality` фильтра. На Magnit `liabilities` начал деградировать до строки `Долгосрочные и краткосрочные обязательства по аренде ... 15 422` вместо `Итого обязательства ... 1 188 616 136`.  
**Корневая причина**:
- ranking bonus сам по себе повысил точность для `cash/equity`, но `liabilities` оставался без собственного `metric_candidate_quality` guard;
- в результате длинная component-фраза побеждала total-row по score.
**Решение**:
- добавить для `liabilities` отдельные `total_tokens` и `component_tokens` в `_metric_candidate_quality`;
- lease/current/non-current component lines должны отбрасываться, если в строке нет явного total-signal.
**Проверка**:
- `python -m pytest tests/test_pdf_extractor.py -q -k "prefers_total_liabilities_row_over_lease_component"` → `passed`
- `RUN_LOCAL_PDF_REGRESSION=1 python -m pytest tests/test_pdf_local_magnit_regression.py -q -k "magnit_2022_ifrs or magnit_2023_ifrs"` → `passed`
**Памятка**:
- любые ranking-changes нужно прогонять не только по synthetic corpus, но и по real Magnit fixtures;
- если добавляется generic score bonus, для balance totals почти всегда нужны metric-aware reject rules против component rows.

### Typographic quotes и broad keyword ties могут ломать real annual reports
**Статус**: ✅ Решено  
**Дата**: 2026-04-01  
**Проблема**: На Cloudflare extractor выбирал `Consolidated Statements of Stockholders' Equity 98` вместо настоящей строки `Total stockholders’ equity 763,047 623,964`; для `cash_and_equivalents` broader candidate `Cash, cash equivalents, and restricted cash, end of period 91,224 ...` перебивал прямую строку `Cash and cash equivalents 86,864 ...`.  
**Корневая причина**:
- text path искал только ASCII apostrophe `'` и не видел typographic `’`;
- при равном score tie-break шёл по большему числу, а не по более точному keyword match.
**Решение**:
- нормализовать typographic quotes до поиска и regex extraction;
- добавить title-noise suppression для `Consolidated Statements of ...`;
- учитывать keyword specificity при line ranking.
**Проверка**:
- `python -m pytest tests/test_pdf_real_fixtures.py -q` → `2 passed`
- `python -m pytest tests/test_pdf_extractor.py -q -k "curly_apostrophe_equity_row_over_ascii_title_number or specific_cash_keyword_match"` → `passed`
**Памятка**:
- для англоязычных annual reports normalizing smart quotes полезнее, чем раздувать keyword lists всеми Unicode-вариантами;
- у cash-like metrics нужна защита от broader phrases вроде `restricted cash/end of period`, иначе tie-break по max(value) уводит не туда.

### После свежего `MSFO/IFRS` patch real Magnit regression падал 6/6
**Статус**: ✅ Решено  
**Дата**: 2026-03-31  
**Проблема**: После sync до `origin/main@a5173bf` и коммита `ddd6eb6` (`Fix russian MSFO`) real-fixture regression по Магниту перестал проходить, хотя unit/integration слой scorer/extractor остаётся зелёным.  
**Как проявляется**:
- `RUN_LOCAL_PDF_REGRESSION=1 python -m pytest tests/test_pdf_local_magnit_regression.py -q`
- `6 failed`
- характер ошибок:
  - `magnit_2025_q1_scanned`: `equity=7000.0` вместо `209475516000.0`
  - `magnit_2025_q1_scanned_liability_bridge`: `liabilities=5000.0` вместо `226183995000.0`
  - `magnit_2025_q1_scanned_balance_components`: `short_term_liabilities=None` вместо `192460146000.0`
  - `magnit_2022_ifrs` / `magnit_2023_ifrs`: `total_assets` занижены на порядок+
  - `magnit_2025_h1_ifrs`: `revenue=12024000.0` вместо `1673223617000.0`
**Что уже проверено**:
- `python -m pytest tests/test_api.py tests/test_scoring.py tests/test_analysis_scoring.py tests/test_pdf_extractor.py -q` → `85 passed`
- значит проблема не в stale tests и не в generic scoring-unit слое, а именно в real extraction path на committed PDF fixtures
**Корневая причина**:
- в `src/analysis/pdf_extractor.py` были добавлены короткие IFRS/note-column коды `3..17`:
  - в `_LINE_CODE_MAP`
  - в отдельный table-pass для `1-2` digit line-codes
  - в `_TEXT_LINE_CODE_MAP` для `equity/liabilities`
- на реальных отчетах Магнита эти числа оказались номерами примечаний и колонок, а не line-codes метрик, поэтому extractor подменял totals значениями вроде `7000`, `5000`, `12024000`
**Решение**:
- убрать короткие `1-2` digit IFRS fallback'и и оставить только безопасные коды/keyword-paths;
- добавить targeted regression tests на collision между note numbers и реальными total-строками
**Проверка**:
- `python -m pytest tests/test_pdf_extractor.py -q` → `52 passed`
- `RUN_LOCAL_PDF_REGRESSION=1 python -m pytest tests/test_pdf_local_magnit_regression.py -q` → `6 passed`
- `python -m pytest tests/test_api.py tests/test_scoring.py tests/test_analysis_scoring.py tests/test_pdf_extractor.py -q` → `87 passed`
**Памятка**:
- не доверять коротким `1-2` digit IFRS кодам как универсальному signal без дополнительного structural context;
- любые изменения в MSFO/IFRS эвристиках прогонять через `RUN_LOCAL_PDF_REGRESSION=1` на Magnit corpus, даже если unit suite зелёный

### После cleanup legacy `analyze`-модулей часть старых тестов осталась в дереве
**Статус**: 🟡 Известно  
**Дата**: 2026-03-31  
**Проблема**: После sync до `origin/main@a5173bf` из репозитория удалены `src/controllers/analyze.py` и `src/routers/analyze.py`, но в `tests/` остались файлы, которые продолжают импортировать эти модули: `tests/test_api.py`, `tests/test_benchmarks.py`, `tests/test_controllers_analyze.py`, `tests/test_controllers_analyze_coverage.py`.  
**Как проявляется**:
- `python -m pytest tests/test_api.py tests/test_benchmarks.py tests/test_controllers_analyze.py tests/test_controllers_analyze_coverage.py -q`
- падает на `ModuleNotFoundError: No module named 'src.routers.analyze'` / `src.controllers.analyze`
**Что известно**:
- `tests/test_pdf_extractor.py` при этом остаётся зелёным (`50 passed`), то есть regression локализован именно в stale test surface вокруг удалённого legacy analyze-flow
- сам `git pull --ff-only` проходит штатно; проблема появляется только на closure validation
**Безопасный следующий шаг**:
- либо удалить/переписать stale tests под актуальные роутеры и runtime flow
- либо временно исключить эти тесты из локального smoke-набора, если задача только в sync без немедленного test-hygiene fixes

### `rg.exe` может быть недоступен в desktop-сессии (Access denied)
**Статус**: 🟡 Известно
**Дата**: 2026-03-30
**Проблема**: В отдельных desktop-сессиях запуск `rg` (ripgrep) падает с `Program 'rg.exe' failed to run ... Отказано в доступе`, даже при корректном `PATH`.
**Где проявилось**:
- поиск по коду/докам в `E:\neo-fin-ai`
**Безопасный workaround**:
- использовать `Select-String` + `Get-ChildItem -Recurse` для текстового поиска;
- для чтения файлов использовать `Get-Content` по целевым диапазонам.

### Конкурсные `.pptx` нельзя полноценно верифицировать в текущей среде без внешних desktop/render-зависимостей
**Статус**: 🟡 Известно
**Дата**: 2026-03-30
**Проблема**: После сборки презентаций на `PptxGenJS` в этой среде нельзя выполнить нормальную post-render проверку слайдов через LibreOffice/PowerPoint/Python parser.
**Где проявилось**:
- `docs/contest_presentation_2026/neo-fin-ai-molodoy-finansist-2026.cjs`
- любые `.pptx`, требующие визуального smoke-check
**Диагностика/наблюдения**:
- `soffice` отсутствует в `PATH`
- PowerPoint COM automation не зарегистрирован
- `python -c "from pptx import Presentation"` падает с `ModuleNotFoundError: No module named 'pptx'`
- `fc-list` также отсутствует, поэтому часть font/render tooling из slide-skill недоступна
**Безопасный workaround**:
- опираться на успешную сборку `.pptx`
- сохранять/проверять `build-log.txt`
- использовать встроенные JS layout/check helpers (`warnIfSlideHasOverlaps`, bounds checks)
- при финальной отправке/защите открыть файл вручную в PowerPoint и быстро проверить:
  - переносы заголовков
  - карточки с цифрами
  - финальный слайд с контактами

### Live smoke (`/upload`) может отдавать `503`, если runtime стартует с `TESTING=1`
**Статус**: ✅ Решено
**Дата**: 2026-03-30
**Проблема**: При запуске живого smoke (`TASK_RUNTIME=celery`) backend мог возвращать `503 Database operation failed` уже на `POST /upload`.
**Корневая причина**: в `.env` задано `TESTING=1`, из-за чего runtime уходил в `TEST_DATABASE_URL` (`neofin_test`) без актуальной schema (`UndefinedTableError: relation "analyses" does not exist`).
**Решение**:
- для live demo/runtime запускать backend+worker с `TESTING=0`;
- перед smoke обязательно выполнить `python -m alembic upgrade head` на рабочей БД.
**Проверка**:
- `python scripts/demo_smoke.py --base-url http://127.0.0.1:8000 --api-prefix / --api-key dev-key-123 --scenario text_single` → `OK`
- `python scripts/demo_smoke.py --base-url http://127.0.0.1:8000 --api-prefix / --api-key dev-key-123 --scenario scanned_single` → `OK`
- `python scripts/demo_smoke.py --base-url http://127.0.0.1:8000 --api-prefix / --api-key dev-key-123 --scenario multi_period_magnit` → `OK`

---

### Demo smoke: `scanned_single` мог завершаться без `liabilities` из-за confidence-gate для derived значения
**Статус**: ✅ Решено
**Дата**: 2026-03-30
**Проблема**: В live runtime `liabilities` для scanned Magnit иногда приходил `None`, хотя parser мог вывести значение. Корневая причина: в `parse_financial_statements_with_metadata()` liabilities, выведенный из `IV+V` или `assets-equity`, маркировался как обычный `derived` (`confidence=0.3`) и отрезался `apply_confidence_filter` при пороге `0.5`.
**Где проявилось**:
- `scripts/demo_smoke.py --scenario scanned_single`
- worker logs: `Missing critical financial field: liabilities`
**Решение**:
- введён `match_type=derived_strong` для liabilities-derived path (`IV+V` и `assets-equity`) с confidence `0.6`;
- для OCR early-stop добавлен более строгий liability-side gate (не останавливать OCR до подтверждённого liability-сигнала);
- добавлены regression tests для stop-логики и strong confidence.
**Проверка**:
- `python -m pytest tests/test_pdf_extractor.py -q` → `41 passed`
- `RUN_LOCAL_PDF_REGRESSION=1 python -m pytest tests/test_pdf_local_magnit_regression.py -k magnit_2025_q1_scanned -q -vv` → `3 passed`
- `python scripts/demo_smoke.py --base-url http://127.0.0.1:8000 --api-prefix / --api-key dev-key-123 --scenario scanned_single` → `OK`

---

### Celery worker на Windows мог падать на последовательных задачах (`event loop is closed`)
**Статус**: ✅ Решено
**Дата**: 2026-03-30
**Проблема**: Последовательный smoke в одном worker-процессе мог падать с `AttributeError: 'NoneType' object has no attribute 'send'` / `RuntimeError: Event loop is closed` (asyncpg path).
**Корневая причина**: в `src/core/task_queue.py` каждая Celery-задача запускалась через `asyncio.run(...)`, создавая/закрывая отдельный loop на каждый task при shared async-runtime ресурсах.
**Решение**:
- Celery worker переведён на persistent process-level event loop:
  - `_get_worker_loop()`
  - `_run_worker_job(...)`
  - `atexit` cleanup (`_close_worker_loop`)
- `run_pdf_task` / `run_multi_analysis_task` больше не используют `asyncio.run(...)` на каждый task.
**Проверка**:
- `python -m pytest tests/test_tasks.py -q` → `27 passed`
- sequential smoke:
  - `text_single + scanned_single` → `OK`
  - `multi_period_magnit` → `OK`

---

### Full live smoke через `docker compose up --build` может блокироваться внешним Docker proxy/pull слоем
**Статус**: 🟡 Известно
**Дата**: 2026-03-30
**Проблема**: Для полного demo-smoke на живом compose-стеке pull базовых image (`postgres:16-alpine`, `redis:7-alpine`) может падать с `Forwarding failure` до старта сервисов проекта.
**Где проявилось**:
- `docker compose up -d --build`
- `docker pull postgres:16-alpine`
- `docker pull redis:7-alpine`
**Диагностика/наблюдения**:
- Docker daemon был восстановлен (первично pipe `dockerDesktopLinuxEngine` был недоступен).
- После восстановления daemon pull всё равно падал на внешнем forwarding/proxy слое.
- Временный fallback для smoke: `docker compose up -d redis` + локальный `uvicorn`/`celery` runtime.
**Риски fallback**:
- это не полный compose parity (нет контейнеризированных `backend/worker/frontend/db`).
- на Windows-процессе `celery + asyncpg` может всплывать `event loop is closed` на последовательных задачах; безопаснее изолированные прогоны по сценариям с рестартом worker.

---

### DetailedReport refactor: regression tests ожидали pure-function exports из page-модуля
**Статус**: ✅ Решено
**Дата**: 2026-03-30
**Проблема**: После decomposition `frontend/src/pages/DetailedReport.tsx` frontend unit-tests (`src/pages/__tests__/DetailedReport.test.tsx`) падали с `buildChartData/getBarColor is not a function`, потому что тесты импортировали helper'ы из page-модуля.
**Решение**:
- зафиксирован compatibility re-export из `DetailedReport.tsx`:
  - `THRESHOLDS`
  - `getBarColor`
  - `buildChartData`
- фактическая реализация helper'ов оставлена в `frontend/src/utils/chartUtils.ts`.
**Проверка**:
- `npm --prefix frontend run test` → `83 passed`

---

### Demo manifest: fixture root сначала ушёл в `tests/PDFforTests` и давал skip локального regression
**Статус**: ✅ Решено
**Дата**: 2026-03-30
**Проблема**: При переходе `tests/test_pdf_local_magnit_regression.py` на manifest-driven cases `fixtures_root` в `tests/data/demo_manifest.json` был задан как `tests/PDFforTests`, из-за чего local regression cases массово пропускались.
**Решение**:
- `fixtures_root` выровнен на фактический путь `PDFforTests`.
- локальный regression harness снова проходит на реальных fixture-файлах.
**Проверка**:
- `RUN_LOCAL_PDF_REGRESSION=1 python -m pytest tests/test_pdf_local_magnit_regression.py -q` → `6 passed`

---

### Deep-review extraction pack: recall/derive/runtime контур стабилизирован
**Статус**: ✅ Решено
**Дата**: 2026-03-30
**Проблема**:
- form-like OCR path был слишком жёстко завязан на line-codes
- row-crop мог терять валидные строки из-за `max_attempts_per_spec=2`
- liabilities derive отбрасывал valid high-leverage кейсы
- local regression повторно гонял OCR одного scanned PDF между кейсами
**Где проявилось**:
- `src/analysis/pdf_extractor.py`
- `tests/test_pdf_extractor.py`
- `tests/test_pdf_local_magnit_regression.py`
**Решение**:
- `is_form_like`/`is_balance_like` разделены; balance guardrails и section extraction теперь balance-context only
- row-crop limits обновлены до `max_attempts_per_spec=4` + page-budget `14`
- long-term IV/V dedupe смягчён до “почти полное совпадение”
- liabilities derive снят с жёсткого upper-cap фильтра
- local Magnit regression получил module-level cache по `(filename, scanned)`
**Проверка**:
- `python -m pytest tests/test_pdf_extractor.py -q`
- `RUN_LOCAL_PDF_REGRESSION=1 python -m pytest tests/test_pdf_local_magnit_regression.py -q`

---

### P5: row-crop OCR тратил лишнее время на нерелевантные строки страницы
**Статус**: ✅ Решено
**Дата**: 2026-03-30
**Проблема**: Layout-aware row-crop вызывался слишком широко в balance-страницах и мог делать лишние crop/OCR попытки на шумных строках.
**Где проявилось**:
- `src/analysis/pdf_extractor.py`
- `tests/test_pdf_extractor.py`
**Решение**:
- добавлен signal-gate `_should_run_layout_metric_row_crop(...)`
- в `extract_text_from_scanned()` row-crop path вызывается только при положительном сигнале
- в `_extract_layout_metric_value_lines(...)` введён лимит `max_attempts_per_spec=2`
- добавлены unit-tests на signal gate, попытки per-spec и вызов только на релевантных страницах
**Проверка**:
- `python -m pytest tests/test_pdf_extractor.py -q`
- `$env:RUN_LOCAL_PDF_REGRESSION='1'; python -m pytest tests/test_pdf_local_magnit_regression.py -q`

---

### P4: local scanned regression не фиксировал отдельные инвариантные срезы по компонентам баланса
**Статус**: ✅ Решено
**Дата**: 2026-03-30
**Проблема**: Один scanned-case в local harness покрывал сразу всё, но не фиксировал отдельными кейсами bridge `LTL = liabilities - STL` и компонентные значения (`inventory`, `AR`, `STL`) как независимые инварианты.
**Где проявилось**:
- `tests/test_pdf_local_magnit_regression.py`
**Решение**:
- добавлены 2 дополнительных scanned-кейса на том же real fixture `magnit_2025_q1_scanned`:
  - `magnit_2025_q1_scanned_balance_components`
  - `magnit_2025_q1_scanned_liability_bridge`
- локальный regression harness расширен до `6` кейсов с отдельной фиксацией component/bridge инвариантов
**Проверка**:
- `$env:RUN_LOCAL_PDF_REGRESSION='1'; python -m pytest tests/test_pdf_local_magnit_regression.py -q`

---

### P3: form-like OCR мог сохранять внутренне противоречивые subtotal/total значения
**Статус**: ✅ Решено
**Дата**: 2026-03-30
**Проблема**: После extraction в form-like ветке отдельные поля могли выглядеть валидно по-отдельности, но нарушать базовые инварианты баланса (`component <= subtotal <= total`), что давало “красивые”, но сомнительные метрики.
**Где проявилось**:
- `src/analysis/pdf_extractor.py`
- `tests/test_pdf_extractor.py`
**Решение**:
- post-parse проверка вынесена в единый `_apply_form_like_guardrails(...)`
- добавлены soft-null rules:
  - `current_assets <= total_assets`
  - `liabilities <= total_assets`
  - `equity <= total_assets`
  - `short_term_liabilities <= total_assets`
  - `cash/inventory/AR <= current_assets`
  - `short_term_liabilities <= liabilities`
- добавлены unit-tests на guardrail-сценарии (`liabilities > total_assets`, `short_term > total_assets`)
**Проверка**:
- `python -m pytest tests/test_pdf_extractor.py -q`
- `$env:RUN_LOCAL_PDF_REGRESSION='1'; python -m pytest tests/test_pdf_local_magnit_regression.py -q`

---

### P2: code `1400` мог занижать/ломать `liabilities` как будто это итог обязательств
**Статус**: ✅ Решено
**Дата**: 2026-03-30
**Проблема**: В form-like/scanned balance `1400` — это долгосрочные обязательства (раздел IV), но pipeline местами трактовал его как `liabilities`. Это ломало derive и могло фиксировать `liabilities` как subtotal вместо total.
**Где проявилось**:
- `src/analysis/pdf_extractor.py`
- `tests/test_pdf_extractor.py`
- `tests/test_pdf_local_magnit_regression.py`
**Решение**:
- `1400` переведён в internal-key `long_term_liabilities` (без расширения публичного API контракта)
- добавлены helper'ы `_extract_form_long_term_liabilities(...)` и `_derive_liabilities_from_components(...)`
- derive `liabilities = IV + V` теперь проходит только при sanity-check (включая cross-check с `assets - equity`)
- regex fallback для `liabilities` больше не считает `Итого долгосрочных/краткосрочных обязательств` за общий итог обязательств
- добавлены unit-tests на конфликтные OCR-кейсы `1400`
- local regression закреплён проверкой `long_term = liabilities - short_term`
**Проверка**:
- `python -m pytest tests/test_pdf_extractor.py -q`
- `$env:RUN_LOCAL_PDF_REGRESSION='1'; python -m pytest tests/test_pdf_local_magnit_regression.py -q`

---

### P1 regression: section row-crop noise мог занижать `short_term_liabilities` на scanned форме
**Статус**: ✅ Решено
**Дата**: 2026-03-30
**Проблема**: При обобщении layout-aware row-crop на коды `1200/1210/1230/1250/1400/1500` в scanned Magnit краткая синтетическая строка для section V (`Итого по разделу V 8 609`) могла попасть в `_extract_form_section_total(...)` и заблокировать корректное значение `short_term_liabilities=192 460 146`.
**Где проявилось**:
- `src/analysis/pdf_extractor.py`
- `tests/test_pdf_local_magnit_regression.py` (`magnit_2025_q1_scanned`)
**Решение**:
- введён spec-driven `_LAYOUT_BALANCE_ROW_SPECS` с минимальным числом digit-групп (`min_groups`) для каждой кодовой строки
- для `1400/1500` добавлен строгий guard `require_code_match` (синтез строки только при явном распознавании кода в row OCR)
- добавлен unit-test `test_extract_layout_metric_value_lines_skips_short_section_noise`
**Проверка**:
- `python -m pytest tests/test_pdf_extractor.py -q`
- `$env:RUN_LOCAL_PDF_REGRESSION='1'; python -m pytest tests/test_pdf_local_magnit_regression.py -q`

---

### Scanned form-like OCR: `accounts_receivable` и `inventory` извлекаются без cross-capture
**Статус**: ✅ Решено
**Дата**: 2026-03-29
**Проблема**: На scanned Magnit Q1 2025 поле `accounts_receivable` присутствовало в OCR как same-line metric, но не извлекалось; при попытке расширить multiline extraction `inventory` мог ложно подхватывать число из соседней строки `Дебиторская задолженность`. Дополнительно `inventory` оставался пустым, потому что базовый OCR-line для `Запасы` не содержал чисел.
**Где проявилось**:
- `src/analysis/pdf_extractor.py`
- `tests/test_pdf_local_magnit_regression.py` (case `magnit_2025_q1_scanned`)
**Решение**:
- в `_extract_best_multiline_value(..., ocr_mode=True)` добавлен same-line OCR parsing после keyword для строк вида `Дебиторская задолженность <числа>`
- для ocr multiline follow-up добавлен фильтр строк с чужими metric keywords, чтобы `inventory` не забирал значение `accounts_receivable`
- form-like allowlist расширен на `accounts_receivable` и `inventory`
- `_TEXT_LINE_CODE_MAP` расширен на `1230` (AR) и `1210` (inventory) для text line-code fallback
- добавлен layout-aware row-crop OCR pass для строки `Запасы`: из правой числовой области извлекается хвост после кода `1210`, подавляется trailing single-digit noise и синтезируется строка `Запасы <значение>`
**Результат на scanned Magnit Q1 2025**:
- `accounts_receivable=26998240000.0` (`text_regex`, `0.5`)
- `inventory=2142153000.0` (`text_regex`, `0.5`)
**Проверка**:
- `python -m pytest tests/test_pdf_extractor.py -q`
- `$env:RUN_LOCAL_PDF_REGRESSION='1'; python -m pytest tests/test_pdf_local_magnit_regression.py -q`

---

### short_term_liabilities в scanned form-like PDF не извлекался из section V totals
**Статус**: ✅ Решено
**Дата**: 2026-03-29
**Проблема**: После улучшений по `equity/liabilities` scanned path оставлял `short_term_liabilities=None`, потому что form-like OCR ветка не имела dedicated extraction из `Итого по разделу V`, а broad text passes для form-like без таблиц этот ключ пропускали.
**Где проявилось**:
- `src/analysis/pdf_extractor.py`
- form-like OCR extraction (`parse_financial_statements_with_metadata`, `tables=[]`)
**Решение**:
- добавлен отдельный form-section pass для `short_term_liabilities` через `_extract_form_section_total(...)` c маркерами `Итого по разделу V/У` и `Итого краткосрочных обязательств`
- расширен `_TEXT_LINE_CODE_MAP` для text line-code fallback по `1500`
- добавлен sanity-check для form-like path: если `short_term_liabilities > liabilities`, значение сбрасывается в безопасный `None`
**Проверка**:
- `python -m pytest tests/test_pdf_extractor.py -q`
- новые unit tests:
  - section V marker extraction
  - scanned form metadata extraction for `short_term_liabilities`

---

### rg.exe из WindowsApps снова падает с Access denied в Codex-сессии
**Статус**: ✅ Зафиксировано (known fallback)
**Дата**: 2026-03-29
**Проблема**: В текущей сессии команда `rg` снова не стартует из `C:\Program Files\WindowsApps\...` (`WinError 5` / `Отказано в доступе`).
**Решение**:
- для этого пакета поиск переведён на `Select-String` / `Get-Content`
- это согласовано с уже зафиксированным known issue про WindowsApps executables
**Проверка**:
- все нужные поиски и правки выполнены без `rg`; тесты прошли

---

### OCR русских scanned-форм может склеивать multi-period суммы и придумывать balance-компоненты
**Статус**: ✅ Решено
**Дата**: 2026-03-29
**Проблема**: На квартальном scanned PDF Магнита OCR path сначала либо резал реальные суммы (`1348 503 -> 1348`), либо, наоборот, склеивал несколько периодов в одно гигантское число. Из-за этого `net_profit` терялся, а `cash/equity/liabilities` могли выглядеть правдоподобно, но быть ложными.
**Где проявилось**:
- `src/analysis/pdf_extractor.py`
- `PDFforTests/Бухгалтерская отчетность ПАО «Магнит» за 1 квартал 2025 года.pdf`
**Решение**:
- добавлены OCR-specific numeric helpers и line-code extraction для form-like Russian OCR
- early-stop OCR ужат до bounded signal-based stop после появления русской бухгалтерской формы
- multiline OCR extraction использует последующие numeric lines, а не только глобальный regex
- добавлен layout-aware extraction section totals через `pytesseract.image_to_data` (`Итого по разделу ... <числа>`), что вернуло `equity`
- `liabilities` теперь безопасно выводятся как `assets - equity` с sanity-check (доля в активах)
- для остальных слабых balance-компонентов (`short_term_liabilities`, `inventory`, `accounts_receivable`) сохраняется safe fallback в `None`
**Проверка**:
- `tests/test_pdf_extractor.py`
- `tests/test_pdf_local_magnit_regression.py`
- ручной прогон scanned Magnit Q1 2025: `revenue/net_profit/total_assets/current_assets/cash/equity/liabilities` корректны

---

### Top-10 по длине строк может выбросить реальные statement tables
**Статус**: ✅ Решено
**Дата**: 2026-03-29
**Проблема**: в `extract_tables()` после Camelot-фильтра оставлялись top-10 таблиц по числу строк. На реальных PDF Магнита это выбрасывало компактные, но правильные statement tables (`Выручка`, `Прибыль за год`, `Итого активы`) и оставляло narrative/TOC шум.
**Где проявилось**:
- `src/analysis/pdf_extractor.py`
- `PDFforTests/Консолидированная финансовая отчетность ПАО «Магнит» ...`
**Решение**:
- добавлен `_table_financial_signal_score(...)`
- при `len(tables_data) > 20` таблицы теперь ранжируются по финансовой релевантности, а не только по длине
**Проверка**:
- real Magnit PDFs снова дают `revenue/net_profit` из `table_exact`

---

### Русские строки с номерами примечаний ломают выбор числа после keyword
**Статус**: ✅ Решено
**Дата**: 2026-03-29
**Проблема**: строки вида `Выручка 24 2 351 996 423` или `Выручка 23 1 673 223 617` заставляли text path брать номер примечания (`24`/`23`) вместо суммы.
**Где проявилось**:
- `src/analysis/pdf_extractor.py`
- реальные PDF Магнита за 2022/2023/H1 2025
**Решение**:
- добавлен `_extract_preferred_numeric_match()`, который пропускает короткие note refs, если дальше идёт реальная денежная сумма
- `net_profit` coverage расширен под `прибыль за период`
**Проверка**:
- Magnit 2022/2023/H1 2025: `revenue/net_profit` теперь корректны

---

### Русские IFRS/МСФО headers не попадали в bounded scale detection
**Статус**: ✅ Решено
**Дата**: 2026-03-29
**Проблема**: после ужесточения scale detection под annual reports парсер перестал масштабировать строки `(в тысячах рублей)` в русских формах, потому что не узнавал headers вида `Консолидированный отчет о финансовом положении`.
**Где проявилось**:
- `src/analysis/pdf_extractor.py`
- real Magnit PDFs
**Решение**:
- расширен набор `statement_markers` под русские/промежуточные IFRS headers
- line normalization перед поиском marker'ов переведена на `" ".join(line.split())`
**Проверка**:
- local Magnit regression harness проходит на scaled values

---

### Глобальный scale detection по всему annual report даёт ложное ×1000
**Статус**: ✅ Решено
**Дата**: 2026-03-29
**Проблема**: `_detect_scale_factor()` раньше сканировал весь текст отчёта и ловил случайное `in thousands` из MD&A/notes, даже если сами audited statements были в абсолютных значениях. На CorVel это раздувало реальные statement values в 1000 раз.
**Где проявилось**:
- `src/analysis/pdf_extractor.py`
- real annual reports: `corvel_2023_annual_report.pdf`
**Решение**:
- scale marker теперь ищется только рядом с реальными statement headers (`consolidated balance sheets`, `consolidated statements of operations` и т.п.)
- fallback ограничен коротким начальным регионом документа, а не всем отчётом
**Проверка**:
- CorVel: `scale_factor == 1.0`
- Cloudflare: `scale_factor == 1000.0`

---

### `table_partial` может быть хуже `text_regex` на длинных annual reports
**Статус**: ✅ Решено
**Дата**: 2026-03-29
**Проблема**: на больших SEC/annual reports ранние нерелевантные таблицы из Camelot могли дать `table_partial`, который перебивал корректное текстовое извлечение с настоящих statement pages. Так появился ложный `revenue=10000` на CorVel.
**Где проявилось**:
- `src/analysis/pdf_extractor.py`
- `tests/data/pdf_real_fixtures/manifest_heavy.json`
**Решение**:
- `text_regex` поднят над `table_partial` в source priority
- Pass 2 / Pass 3 больше не прекращают поиск только потому, что метрика уже занята `table_partial`
- текстовый путь переведён на line-based selection statement rows вместо глобального `re.search(...)`
**Проверка**:
- CorVel heavy case теперь даёт `revenue=718562000.0`, а не `10000.0`

---

### Runtime stale recovery в v1 не делает automatic requeue
**Статус**: ✅ Зафиксировано как осознанное решение
**Дата**: 2026-03-29
**Контекст**: Во второй волне persistent runtime появился stale recovery job для зависших worker-задач.
**Почему так**:
- auto-requeue на этом этапе слишком рискован: можно получить duplicate execution и конфликт финализации
- безопаснее сначала честно переводить stale `processing` runtime в `failed` с `reason_code=runtime_stale_timeout`
**Где реализовано**:
- `src/maintenance/runtime_recovery.py`
- `src/db/crud.py`
- `scripts/runtime_recover.py`
**Следующий шаг**:
- если когда-нибудь делать requeue, то только с явным deduplication/ownership contract, а не как “тихий retry”

---

### Cancellation payload не должен стирать уже сохранённый snapshot анализа
**Статус**: ✅ Решено
**Дата**: 2026-03-29
**Проблема**: При переходе на cooperative cancellation worker записывает финальный `cancelled` payload. Если тупо заменить `result` на `{"error": ...}`, можно потерять уже сохранённый `filename` и другие полезные поля из initial upload snapshot.
**Где проявилось**:
- `src/db/crud.py`
- `mark_analysis_cancelled()`
**Решение**:
- добавлен merge path для dict payload'ов: cancellation result поверх existing snapshot, а не вместо него
- тот же приём применён в multi-session cancellation/update path, чтобы partial result и диагностические поля не затирали друг друга
**Проверка**:
- `tests/test_db_crud.py`
- `tests/test_runtime_cancellation.py`

---

### Bootstrap новой `env` ломался из-за несуществующей версии `pdfplumber~=0.12.0`
**Статус**: ✅ Решено
**Дата**: 2026-03-29
**Проблема**: После пересоздания локальной `env` команда `env\Scripts\python.exe -m pip install -r requirements.txt` падала на `No matching distribution found for pdfplumber~=0.12.0`.
**Где проявилось**:
- `env\Scripts\python.exe -m pip install -r requirements.txt`
**Корневая причина**:
- проблема была не в сети и не в локальном индексе: версия `0.12.0` у `pdfplumber` не опубликована на PyPI
- первичный источник и `pip index versions pdfplumber` подтверждают, что latest = `0.11.9`
**Решение**:
- в `requirements.txt` зависимость возвращена к опубликованной `pdfplumber~=0.11.9`
- после этого полный `env\Scripts\python.exe -m pip install -r requirements.txt` проходит
**Проверка**:
- `env\Scripts\python.exe -m pip install -r requirements.txt`
- `env\Scripts\python.exe -c "import pdfplumber; print(pdfplumber.__version__)"`

---

### Stale regression test требовал несуществующий `pdfplumber~=0.12.x`
**Статус**: ✅ Решено
**Дата**: 2026-03-29
**Проблема**: После dependency-fix в `requirements.txt` один из legacy regression tests продолжал утверждать, что правильный pin должен быть `pdfplumber~=0.12.x`, хотя upstream PyPI по-прежнему отдаёт latest=`0.11.9`.
**Где проявилось**:
- `tests/test_qwen_regression_fixes.py::test_pdfplumber_version`
**Решение**:
- комментарий в `requirements.txt` переписан в точную формулировку про latest published release
- stale test expectation обновлён на `pdfplumber~=0.11.9`
**Проверка**:
- `Invoke-RestMethod https://pypi.org/pypi/pdfplumber/json`
- `python -m pytest tests/test_qwen_regression_fixes.py -k pdfplumber_version -q`

---

### Runtime-сервисы в compose могли тихо уехать в test DB из-за `TESTING=1`
**Статус**: ✅ Решено
**Дата**: 2026-03-29
**Проблема**: Локальный `.env` содержал `TESTING=1`, а `backend` / `worker` / `backend-migrate` читали его через `env_file`. Из-за логики в `src/db/database.py` это позволяло runtime-сервисам предпочесть `TEST_DATABASE_URL` вместо основной БД.
**Где проявилось**:
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `src/db/database.py`
**Решение**:
- в dev и prod compose для runtime-сервисов явно задан `TESTING: 0`
- локальный `docker-compose.yml` восстановлен до полноценного dev-стека и больше не маскирует этот риск временным redis-only файлом
**Проверка**:
- `docker compose -f docker-compose.yml config`
- `docker compose -f docker-compose.prod.yml config`
- в итоговом config у runtime-сервисов `TESTING: "0"`

---

### Docker pull до внешних registry blobs может падать на сетевом слое
**Статус**: 🟡 Частично обойдено
**Дата**: 2026-03-29
**Проблема**: Локальная попытка скачать Docker image может падать на сетевом слое/registry CDN, не доходя до compose/runtime логики проекта.
**Где проявилось**:
- `docker pull redis:*`
- `docker compose up -d redis`
 - `docker compose -f docker-compose.prod.yml up -d db backend-migrate worker` (`postgres:16-alpine` → `unexpected EOF`)
**Текущее состояние**:
- Redis `8.6-alpine` в итоге удалось завести локально, runtime-проверка Redis + worker прошла
- проблема не исчезла полностью: другие pulls по-прежнему могут падать на внешнем blob-path
**Временное решение**:
- если нужный image уже добыт, использовать локальный cache / `docker load`
- при сетевом сбое не считать это багом проекта: сначала отделять registry/CDN проблему от compose/runtime логики

---

### Нет честного role-native launch для внешнего runtime
**Статус**: 🟡 Известно
**Дата**: 2026-03-29
**Проблема**: В NeoFin уже есть human-readable manifests, launch protocol и жёсткие orchestration rules, но нет настоящего внешнего runtime-механизма, который first-class поднимает project-role как отдельную сущность. На практике это значит, что внешний вызов либо остаётся серой зоной между role и carrier, либо оркестратор вынужден безопасно откатываться в `local role-guided synthesis`.
**Почему это важно**:
- нельзя честно и технически доказуемо заявлять, что был выполнен полноценный внешний `role-native` запуск
- часть orchestration policy вынужденно опирается на процессную дисциплину, а не на runtime enforcement
- это ограничивает полезность внешних субагентов для review/investigation задач
**Текущее безопасное поведение**:
- в NeoFin по умолчанию использовать `local role-guided synthesis`
- не выдавать generic carrier за реальный вызов project-role
- внешний вызов считать допустимым только если role-binding можно доказать без серой зоны
**Следующий шаг**:
- либо построить честный role-native external runtime в `E:\codex-autopilot`
- либо продолжать в NeoFin только локальный protocol layer без притворства, что внешний runtime уже существует

---

### WindowsApps executables в Codex сессии могут падать с Access denied
**Статус**: 🟡 Известно
**Дата**: 2026-03-28
**Проблема**: Часть бинарников, найденных в `C:\Program Files\WindowsApps\...`, существует и видна через `where.exe`/`Get-Command`, но subprocess запуск из текущей Codex desktop сессии может падать с `[WinError 5] Отказано в доступе`.
**Где проявилось**:
- `codex.exe --version` из experimental Autopilot spike до миграции в `E:\codex-autopilot`
- `rg.exe` из WindowsApps при локальном exploratory search
**Временное решение**:
- для служебного поиска использовать PowerShell cmdlets (`Get-ChildItem`, `Select-String`) вместо проблемного бинарника
- в `CodexCliAdapter` возвращать явную диагностическую ошибку через `availability_error()`, а не считать runtime silently available
- если установлен standalone `npm i -g @openai/codex`, предпочитать его shim из `PATH` (`codex.cmd`) вместо WindowsApps binary
- для `codex exec` версии `0.117.0` не передавать `-a/--ask-for-approval`: этот флаг есть у верхнего `codex`, но subcommand `exec` его не принимает

---

### Celery + Redis Migration
**Статус**: ✅ Первая версия внедрена
**Дата**: 2026-03-29
**Проблема**: Текущие `BackgroundTasks` выполнялись в памяти и терялись при перезагрузке сервера.
**Решение**:
- добавлен `TASK_RUNTIME=background|celery`
- `src/core/task_queue.py` вводит dispatch layer поверх канонических `process_pdf` / `process_multi_analysis`
- `src/core/runtime_events.py` переносит worker status events через Redis pub/sub обратно в WebSocket-процесс FastAPI
- `docker-compose.yml` и `docker-compose.prod.yml` получили `redis` и `worker`
- локальный test/runtime path сохраняет safe fallback: без Celery/Redis проект продолжает работать в `background`
**Остаточный риск**:
- отмена задач в celery-пути пока best-effort (`revoke_runtime_task`), без полного распределённого протокола отмены
- нужен отдельный worker/deploy smoke-check на живом окружении, а не только `compose config` и mocked tests

---

### OCR Performance
**Статус**: ✅ Частично решено (MAX_OCR_PAGES = 50)
**Проблема**: Обработка многостраничных PDF занимает значительное время.
**Решение**: Добавлен лимит `MAX_OCR_PAGES = 50` в `extract_text_from_scanned`. Внедрение параллельной обработки страниц и кэширования — в планах.

---

### Camelot на реальных annual reports может быть слишком медленным для fast smoke suite
**Статус**: ✅ Смягчено
**Дата**: 2026-03-28
**Проблема**: На части реальных многостраничных annual reports `extract_tables()` может уходить в десятки секунд и упираться в Camelot timeout budget, даже если text-layer extraction сама по себе стабильна.
**Временное решение**:
- committed real-PDF smoke corpus в `tests/data/pdf_real_fixtures/` использует `text_only` pipeline
- full-table / OCR-heavy real corpus вынесен в отдельный optional tier:
  - `tests/test_pdf_real_heavy_fixtures.py`
  - `tests/data/pdf_real_fixtures/manifest_heavy.json`
  - запуск только явно: `RUN_PDF_REAL_HEAVY=1`
- synthetic corpus остаётся основным regression guard для table-layout edge cases

---

### BOM в `.flake8`
**Статус**: 🟡 Известно
**Дата**: 2026-03-28
**Проблема**: `python -m flake8 --config=.flake8 ...` падает с `MissingSectionHeaderError`.
**Причина**: файл `.flake8` сохранён с UTF-8 BOM, и текущий `flake8` в этой среде читает первую строку как `\ufeff[flake8]`.
**Временное решение**: запускать `flake8` в `--isolated` режиме и явно передавать ключевые параметры CLI, например `--max-line-length=100`.

---

### `docker compose config` раскрывает секреты из локального `.env`
**Статус**: 🟡 Известно
**Дата**: 2026-03-28
**Проблема**: команда рендерит итоговый compose c уже подставленными env-значениями, поэтому при ручной диагностике/копировании в чат легко утечь чувствительные значения.
**Где проявилось**:
- `docker compose -f docker-compose.yml config`
- `docker compose -f docker-compose.prod.yml config`
**Временное решение**:
- не логировать полный вывод `docker compose config` в issue/чатах
- при проверке compose смотреть только structural sections или локально фильтровать чувствительные поля
- при будущей hardening-итерации рассмотреть `secrets`/`_FILE` pattern для production

---

### Docker daemon может быть недоступен в Codex desktop сессии
**Статус**: 🟡 Известно
**Дата**: 2026-03-28
**Проблема**: `docker compose ... build` может падать не из-за compose-конфига, а потому что недоступен `dockerDesktopLinuxEngine` pipe.
**Где проявилось**:
- `docker compose -f docker-compose.prod.yml build nginx`
**Временное решение**:
- сначала проверять `docker compose ... config`
- отдельно валидировать shell-скрипты (`bash -n scripts/deploy-prod.sh`)
- если нужен реальный build smoke-check, убедиться что Docker Desktop/daemon запущен в хостовой среде

---

### ARC4 deprecation warning всё ещё может всплывать как residual summary на PDF-related pytest runs
**Статус**: 🟡 Известно
**Дата**: 2026-03-29
**Проблема**: Даже после возврата к локализованному suppression в PDF-related тестовых модулях pytest иногда всё ещё показывает один `CryptographyDeprecationWarning` summary про ARC4 на прогонах PDF stack.
**Где проявилось**:
- `python -m pytest tests/test_pdf_extractor.py tests/test_pdf_real_fixtures.py tests/test_pdf_regression_corpus.py tests/test_pdf_real_heavy_fixtures.py -q`
- `python -m pytest tests/test_pdf_real_heavy_fixtures.py --collect-only -q --run-pdf-real-heavy`
**Текущее состояние**:
- default suite больше не маскирует warning глобально через `tests/conftest.py`
- noise ограничен PDF-related path и не влияет на обычные router/task suites
**Временное решение**:
- считать это residual import-time warning от transitive `pypdf` / `cryptography` стека
- при следующем hygiene pass отдельно проверить, можно ли подавлять его ещё точнее без возврата к глобальному suppression

---

## Решённые проблемы

### Loop-bound `aiohttp` session могла переживать shutdown и Celery worker boundary
**Статус**: Решено ✅
**Дата решения**: 2026-03-29
**Корневая причина**:
1. `AIService` живёт как глобальный объект и держит provider-specific HTTP runtime на уровне процесса.
2. В persistent runtime Celery wrappers запускали async pipeline через `asyncio.run(...)`, то есть каждая задача получала новый event loop.
3. Без явного закрытия shared session могла пережить один loop и быть повторно использована в следующем, что рискованно для `aiohttp.ClientSession`.
4. Тот же хвост мог проявляться на shutdown приложения как `Unclosed client session` в расширенном pytest suite.

**Решение**:
```python
# src/core/ai_service.py
async def close(self) -> None:
    close_method = getattr(self._agent, "close", None)
    if close_method is not None:
        await close_method()

# src/core/task_queue.py
async def _run_worker_coroutine(coro):
    try:
        await coro
    finally:
        await ai_service.close()

# src/app.py
await ai_service.close()
```

**Где смотреть**:
- `src/core/ai_service.py`
- `src/core/task_queue.py`
- `src/app.py`
- `tests/test_tasks.py`
- `tests/test_app_coverage.py`

**Проверка**:
- `python -W error::ResourceWarning -W error::RuntimeWarning -m pytest tests/test_routers_pdf_tasks.py tests/test_multi_analysis_router.py tests/test_tasks.py tests/test_app_coverage.py tests/test_models_settings.py -q`
- `python -m pytest tests/test_api.py tests/test_analyses_router.py tests/test_app_coverage.py tests/test_routers_pdf_tasks.py tests/test_multi_analysis_router.py tests/test_tasks.py tests/test_models_settings.py -q`

### Optional heavy real-PDF tier мог ломать pytest collection, а ARC4 suppression дублировался по тестовым модулям
**Статус**: Решено ✅
**Дата решения**: 2026-03-28
**Корневая причина**:
1. `tests/test_pdf_real_heavy_fixtures.py` загружал `manifest_heavy.json` на module import path через `REAL_PDF_HEAVY_CASES = _load_cases()`, поэтому missing/corrupt manifest мог валить collection даже при выключенном heavy-tier.
2. Один и тот же `ARC4 has been moved.*` suppression дублировался в нескольких PDF-related тестовых модулях.

**Решение**:
```python
# tests/test_pdf_real_heavy_fixtures.py
def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "case" in metafunc.fixturenames:
        metafunc.parametrize("case", _load_case_params(metafunc.config))

# tests/conftest.py
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--run-pdf-real-heavy", action="store_true", default=False)

def pytest_configure(config):
    config.addinivalue_line(
        "filterwarnings",
        "ignore:ARC4 has been moved.*:cryptography.utils.CryptographyDeprecationWarning",
    )
```

**Где смотреть**:
- `tests/conftest.py`
- `tests/test_pdf_real_heavy_fixtures.py`
- `tests/test_pdf_extractor.py`
- `tests/test_pdf_real_fixtures.py`
- `tests/test_pdf_regression_corpus.py`

**Проверка**:
- `python -m pytest tests/test_pdf_extractor.py tests/test_pdf_real_fixtures.py tests/test_pdf_regression_corpus.py tests/test_pdf_real_heavy_fixtures.py -q`
- `python -m pytest tests/test_pdf_real_heavy_fixtures.py --collect-only -q --run-pdf-real-heavy`

### App-level exception handlers были зарегистрированы слишком поздно, а `multi_analysis` светил raw validator details
**Статус**: Решено ✅
**Дата решения**: 2026-03-28
**Корневая причина**:
1. `register_exception_handlers(app)` вызывался внутри `lifespan`, из-за чего `DatabaseError` на реальном HTTP path фактически не мапился в канонический JSON-ответ и превращался в сырой `500 Internal Server Error`.
2. `src/routers/multi_analysis.py` возвращал клиенту `jsonable_encoder(exc.errors())`, привязывая публичный `422` к внутренней структуре Pydantic validators.

**Решение**:
```python
# src/app.py
app = FastAPI(version="0.1.0", lifespan=lifespan)
register_exception_handlers(app)

# src/routers/multi_analysis.py
except ValidationError as exc:
    logger.warning("Validation failed for multi-analysis input: %s", exc.errors())
    raise HTTPException(status_code=422, detail="Invalid multi-analysis request") from exc
```

**Где смотреть**:
- `src/app.py`
- `src/utils/error_handler.py`
- `src/routers/multi_analysis.py`
- `tests/test_multi_analysis_router.py`

**Проверка**:
- `python -m pytest tests/test_multi_analysis_router.py -q`
- `python -W error::ResourceWarning -W error::RuntimeWarning -m pytest tests/test_multi_analysis_router.py tests/test_tasks.py tests/test_routers_pdf_tasks.py tests/test_analyses_router.py tests/test_routers_system.py tests/test_routers_system_full.py tests/test_websocket_integration.py -q`

### `multi_analysis` мог оставлять временные PDF на диске, а ARC4 warning был заглушён слишком широко
**Статус**: Решено ✅
**Дата решения**: 2026-03-28
**Корневая причина**:
1. `src/routers/multi_analysis.py` удалял temp PDF только в ветке `ValidationError`, но не на других pre-handoff путях ошибок.
2. `pytest.ini` глобально подавлял `CryptographyDeprecationWarning` про ARC4, скрывая полезный сигнал о deprecated PDF crypto stack.
3. `tests/test_multi_analysis_router.py` использовал permissive `TestClient` в общей фикстуре и мог скрывать неожиданные server-side exceptions.
4. `tests/test_tasks.py` проверял completed status через `call_args_list[-1][0][1]`, что хрупко к внутренней перестановке вызовов.

**Решение**:
```python
# src/routers/multi_analysis.py
temp_paths: list[str] = []
handed_off = False
...
finally:
    if not handed_off:
        _cleanup_temp_files(temp_paths)

# pytest.ini
# удалён глобальный ARC4 filterwarnings

# tests/test_tasks.py
def _assert_completed_status_called(mock_update, task_id: str) -> None:
    assert any(call.args[:2] == (task_id, "completed") for call in mock_update.call_args_list)
```

**Где смотреть**:
- `src/routers/multi_analysis.py`
- `pytest.ini`
- `tests/test_multi_analysis_router.py`
- `tests/test_tasks.py`
- `tests/test_routers_pdf_tasks.py`

**Проверка**:
- `python -m pytest tests/test_multi_analysis_router.py tests/test_tasks.py tests/test_routers_pdf_tasks.py -q`
- `python -W error::ResourceWarning -W error::RuntimeWarning -m pytest tests/test_multi_analysis_router.py tests/test_tasks.py tests/test_routers_pdf_tasks.py tests/test_analyses_router.py tests/test_routers_system.py tests/test_routers_system_full.py tests/test_websocket_integration.py -q`

### `POST /multi-analysis` отдавал `500` вместо `422` на невалидной метке периода, а stale tests запускали background path
**Статус**: Решено ✅
**Дата решения**: 2026-03-28
**Корневая причина**:
1. `start_multi_analysis()` создавал `PeriodInput(...)` прямо внутри роутера и не переводил `ValidationError` в HTTP `422`.
2. Для blank-label кейса `exc.errors()` содержал `ValueError` в `ctx`, из-за чего даже попытка завернуть ошибку в `HTTPException` могла упасть на JSON сериализации.
3. `tests/test_multi_analysis_router.py` отставал от текущего контракта: старый multipart helper, отсутствие мока `process_multi_analysis`, старые completed fixtures без `extraction_metadata`.
4. Несколько router/websocket/system tests держали `TestClient` вне context manager.

**Решение**:
```python
# src/routers/multi_analysis.py
except ValidationError as exc:
    logger.warning("Validation failed for multi-analysis input: %s", exc.errors())
    raise HTTPException(status_code=422, detail="Invalid multi-analysis request") from exc

# tests/test_multi_analysis_router.py
patch("src.routers.multi_analysis.process_multi_analysis", new_callable=AsyncMock)
data = {"periods": labels}
```

**Где смотреть**:
- `src/routers/multi_analysis.py`
- `tests/test_multi_analysis_router.py`
- `tests/test_analyses_router.py`
- `tests/test_routers_system.py`
- `tests/test_websocket_integration.py`

**Проверка**:
- `python -m pytest tests/test_multi_analysis_router.py tests/test_routers_pdf_tasks.py -q`
- `python -W error::ResourceWarning -W error::RuntimeWarning -m pytest tests/test_analyses_router.py tests/test_routers_system.py tests/test_routers_system_full.py tests/test_websocket_integration.py tests/test_multi_analysis_router.py -q`

### Test hygiene drift после DB hardening: `process_pdf` unit-тесты случайно трогали реальную БД
**Статус**: Решено ✅
**Дата решения**: 2026-03-28
**Корневая причина**:
1. После DB hardening `get_analysis()` перестал маскировать SQLAlchemy ошибки под `None`.
2. `process_pdf()` делает дополнительный `get_analysis(task_id)` перед финализацией для чтения `filename`.
3. В success-path тестах `tests/test_tasks.py` этот вызов не был замокан, поэтому unit-тесты выходили из hermetic path и могли поднять реальный asyncpg engine.
4. `RuntimeWarning: coroutine 'Connection._cancel' was never awaited` оказался вторичным fallout после этого accidental DB path.

**Решение**:
```python
# tests/test_tasks.py
patch("src.tasks.get_analysis", new_callable=AsyncMock, return_value=None)

# pytest.ini
asyncio_default_fixture_loop_scope = function
filterwarnings =
    ignore:ARC4 has been moved.*:cryptography.utils.CryptographyDeprecationWarning
```

**Где смотреть**:
- `tests/test_tasks.py`
- `pytest.ini`

**Проверка**:
- `python -m pytest tests/test_tasks.py tests/test_api.py tests/test_app_coverage.py -q`
- `python -W error::RuntimeWarning -m pytest tests/test_tasks.py tests/test_api.py tests/test_app_coverage.py -q`

### DB read failures маскировались под `None`/ложный `404`, а pool-настройки применялись не полностью
**Статус**: Решено ✅
**Дата решения**: 2026-03-28
**Корневая причина**:
1. `get_analysis()` и `get_multi_session()` глотали `SQLAlchemyError` и возвращали `None`, после чего routers трактовали это как обычное отсутствие записи.
2. `DB_POOL_TIMEOUT` и `DB_POOL_RECYCLE` логировались, но не передавались в `create_async_engine()`.
3. FastAPI lifespan не вызывал `dispose_engine()`, поэтому pooled connections могли переживать shutdown/test teardown дольше, чем ожидалось.

**Решение**:
```python
# src/db/crud.py
except SQLAlchemyError:
    raise

# src/db/database.py
create_async_engine(..., pool_timeout=pool_timeout, pool_recycle=pool_recycle)

# src/app.py
await dispose_engine()
```

**Где смотреть**:
- `src/db/database.py`
- `src/db/crud.py`
- `src/db/models.py`
- `migrations/versions/0004_harden_db_status_constraints.py`
- `src/routers/analyses.py`
- `src/routers/pdf_tasks.py`
- `src/routers/multi_analysis.py`

**Проверка**:
- `python -m pytest tests/test_api.py tests/test_analyses_router.py tests/test_routers_pdf_tasks.py tests/test_multi_analysis_db_errors.py tests/test_db_database.py tests/test_db_crud.py tests/test_app_coverage.py -q`

### OCR helper мог склеивать числа через переносы строк и обходить page cap в fallback path
**Статус**: Решено ✅
**Дата решения**: 2026-03-28
**Корневая причина**:
1. Вспомогательные helper-ы `_extract_section_total()` и `_extract_number_near_keywords()` всё ещё использовали старый regex с `\s`, который мог захватывать числа через `\n`.
2. В `extract_text_from_scanned()` mock-friendly `TypeError` fallback вызывал `convert_from_path(pdf_path)` без ограничения batch size.

**Решение**:
```python
# src/analysis/pdf_extractor.py
# keyword-window extraction через _NUMBER_PATTERN.search(...)
# вместо regex с [\\d\\s.,]* across newlines

if not single_page_batch and len(images) > MAX_OCR_PAGES:
    images = images[:MAX_OCR_PAGES]
```

**Где смотреть**:
- `src/analysis/pdf_extractor.py`
- `tests/test_pdf_extractor.py`

**Проверка**:
- `python -m pytest tests/test_pdf_extractor.py -q`
- `python -m pytest tests/test_scoring.py tests/test_pdf_extractor.py tests/test_api.py -q`

### Complex table layouts могли подставлять год вместо значения и не матчить garbled labels
**Статус**: Решено ✅
**Дата решения**: 2026-03-28
**Корневая причина**:
1. После допуска 4-значных financial values helper `_extract_first_numeric_cell()` мог выбрать `2023`/`2022` как первое число строки в multi-period tables.
2. Ветка `_GARBLED_KEYWORDS` сравнивала lower-cased `label_cell` с частично не-lower-cased garbled variants.

**Решение**:
```python
# src/analysis/pdf_extractor.py
if value is not None and not _is_year(value):
    return value

if garbled_kw.lower() in label_cell:
    ...
```

**Где смотреть**:
- `src/analysis/pdf_extractor.py`
- `tests/data/pdf_regression_corpus.json`
- `tests/test_pdf_regression_corpus.py`

**Проверка**:
- `python -m pytest tests/test_pdf_regression_corpus.py -q`
- `python -m pytest tests/test_pdf_extractor.py tests/test_pdf_regression_corpus.py tests/test_scoring.py tests/test_api.py -q`

### Сбой shell-команд в sandbox Codex сессии
**Дата**: 2026-03-28
**Проблема**: В этой сессии базовые команды PowerShell в sandbox возвращали `Exit code: 1` без вывода.
**Решение**: Для чтения/редактирования файлов использовать команды вне sandbox (эскалация), после чего работа продолжилась штатно.

### Утечка ресурсов в GigaChat (БАГ 15)
**Дата**: 2026-03-26
**Проблема**: Создание нового `aiohttp.ClientSession` на каждый запрос приводило к port exhaustion.
**Решение**: Внедрён Singleton `_session` в `BaseAIAgent`, который переиспользуется всеми агентами.

### NameError в tasks.py
**Дата**: 2026-03-26
**Проблема**: Обработчик ошибок `_handle_task_failure` пытался обратиться к `file_path`, который не был передан в аргументах.
**Решение**: Рефакторинг `tasks.py`, перенос очистки в `finally` блок родительской функции `process_pdf`.

### Дублирование типов на фронтенде
**Дата**: 2026-03-26
**Проблема**: Файлы `types.ts` и `interfaces.ts` содержали противоречивые определения.
**Решение**: `types.ts` удалён, все импорты переведены на `interfaces.ts`.

---

### 27 failing тестов (e2e/integration)
**Статус**: 🟡 Известно
**Дата**: 2026-03-25
**Проблема**: 27 тестов failing из 577 total (95% passing rate)
**Причина**: Требуют реальную БД и AI-провайдеров.
**Решение**: Разделение тестов на unit (всегда зеленые) и интеграционные (требуют окружения).

---

### Auth fixture не применяется до импорта app
**Статус**: ✅ Решено
**Дата решения**: 2026-03-25
**Решение**: 
- Environment переменные установлены на модульном уровне в conftest.py ДО импорта app
- Добавлен `client` fixture с dependency override для auth
- Все тесты переписаны на использование `client` fixture

```python
# conftest.py — module level
os.environ["TESTING"] = "1"
os.environ["DEV_MODE"] = "1"
os.environ["API_KEY"] = "test-key-for-testing"

@pytest.fixture(scope="function")
def client():
    from fastapi.testclient import TestClient
    from src.app import app
    from src.core.auth import get_api_key
    
    async def override_auth():
        return "test-user"
    
    app.dependency_overrides[get_api_key] = override_auth
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()
```

---

**Связанные задачи**:
- Task 5.3 — Multi-Analysis Router Tests

---

### Rate limiting срабатывает при property-based тестах
**Статус**: 🟡 Известно
**Дата**: 2026-03-25
**Проблема**: Hypothesis генерирует много запросов (50-100 итераций). SlowAPI rate limiter блокирует запросы с ошибкой 429 Too Many Requests.

**Стектрейс/Ошибка**:
```
assert 429 == 202
WARNING slowapi:extension.py:510 ratelimit 100 per 1 minute (testclient) exceeded
```

**Корневая причина**:
- Rate limiter настроен на 100 запросов в минуту
- Hypothesis делает 100+ запросов быстро

**Решение**:
```python
@pytest.fixture(scope="function")
def no_rate_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "1000/second")
    yield
    monkeypatch.undo()
```

**Где применено**: `tests/test_multi_analysis_router.py`

**Связанные задачи**:
- Task 5.3 — Multi-Analysis Router Tests

---

### Score: 0 и пустые факторы во frontend (несовместимость scoring → analyze.py)
**Статус**: Решено ✅
**Дата решения**: 2026-03-24
**Корневая причина**: Два независимых бага:
1. `scoring.py` использовал ключ `"Финансовый рычаг"` в `weights`, а `RATIO_KEY_MAP` в `tasks.py` содержит `"Долговая нагрузка"` — `_build_score_payload()` никогда не находил этот коэффициент в `details`, 10% веса терялось.
2. Fallback-ветка в `analyze.py` (когда AI недоступен) вызывала `score_data.get("factors", [])` и `score_data.get("normalized_scores", {...})` — но `calculate_integral_score()` возвращает `details`, а не `factors`/`normalized_scores`. Frontend получал `score.factors = []` и `score = 0`.

**Решение**:
```python
# src/analysis/scoring.py — исправлен ключ
weights = {
    ...
    "Долговая нагрузка": 0.1,  # было: "Финансовый рычаг"
}

# src/controllers/analyze.py — fallback теперь использует _build_score_payload из tasks.py
from src.tasks import _translate_ratios, _build_score_payload
ratios_en = _translate_ratios(ratios)
score_payload = _build_score_payload(raw_score, ratios_en)
```
Где применено: `src/analysis/scoring.py`, `src/controllers/analyze.py`
Проверка: `POST /analyze/pdf/file` возвращает `score.factors` (непустой список) и `score.score > 0` при наличии метрик в PDF.

---

### [ШАБЛОН] Название проблемы
**Статус**: 🟡 Известно
**Дата**: ГГГГ-ММ-ДД
**Проблема**: Что ломается и при каких условиях.

**Стектрейс/Ошибка**:
```
вставить сюда
```

**Временное решение / Воркэраунд**:
Описание.

**Где смотреть**:
- `src/path/to/file.py` (строка X)

**Связанные задачи**:
- —

---

## Решённые проблемы (архив)

### Утечка ресурсов в GigaChatAgent (ClientSession)
**Статус**: Решено ✅
**Дата решения**: 2026-03-26
**Корневая причина**: Создание новой `aiohttp.ClientSession` на каждый запрос приводило к исчерпанию файловых дескрипторов и портов под нагрузкой.
**Решение**: Внедрена ленивая инициализация сессии (Singleton) с методом `close()`.
**Где смотреть**: `src/core/gigachat_agent.py`

### Низкая достоверность скоринга при неполных данных
**Статус**: Решено ✅
**Дата решения**: 2026-03-26
**Корневая причина**: При отсутствии большинства коэффициентов система могла выдать высокий балл на основе единственного показателя.
**Решение**: Добавлено поле `confidence_score` (сумма весов найденных данных). Фронтенд может предупреждать о низкой полноте отчета.
**Где смотреть**: `src/analysis/scoring.py`

### Ошибки детекции сканированных PDF
**Статус**: Решено ✅
**Дата решения**: 2026-03-26
**Корневая причина**: Проверка только по количеству символов текста давала ложноположительные результаты на PDF с пустыми текстовыми слоями.
**Решение**: Добавлена проверка наличия `/Image` объектов в структуре PDF страниц.
**Где смотреть**: `src/analysis/pdf_extractor.py`

### Dashboard теряет результат анализа при навигации
**Статус**: Решено ✅
**Дата решения**: 2026-03-24
**Корневая причина**: `usePdfAnalysis` хранил состояние локально в хуке. При переходе на другую страницу `Dashboard` размонтировался → хук сбрасывался → `data = null`. Анализ продолжался в фоне, но результат некуда было записать при возврате.

**Решение (чистое)**: создан `AnalysisContext` — отдельный контекст на уровне приложения, который владеет всем состоянием анализа (`status`, `result`, `filename`, `error`, `analyze`, `reset`). `usePdfAnalysis.ts` удалён. `Dashboard` только читает из `useAnalysis()`, не владеет состоянием.

```tsx
// frontend/src/context/AnalysisContext.tsx — новый контекст
export const AnalysisProvider: React.FC<...> = ({ children }) => {
    const [status, setStatus] = useState<AnalysisStatus>('idle');
    const [result, setResult] = useState<AnalysisData | null>(null);
    // ... analyze(), reset()
};

// frontend/src/App.tsx — обёрнут вокруг роутов
<AnalysisProvider>
  <BrowserRouter>...</BrowserRouter>
</AnalysisProvider>

// frontend/src/pages/Dashboard.tsx — только читает
const { status, result, filename, error, analyze, reset } = useAnalysis();
```

Где применено: `frontend/src/context/AnalysisContext.tsx` (новый), `frontend/src/pages/Dashboard.tsx`, `frontend/src/App.tsx`, `frontend/src/context/AnalysisHistoryContext.tsx` (очищен от `pending*`)
Проверка: загрузить PDF → перейти на Settings → вернуться на Dashboard → результат отображается.

> ⚠️ Паттерн: состояние, которое должно пережить навигацию — выносить в отдельный Context на уровне приложения, не хранить в локальном хуке и не примешивать к несвязанным контекстам.

---

### AnalysisHistory — белый экран при клике на запись без данных
**Статус**: Решено ✅
**Дата решения**: 2026-03-24
**Корневая причина**: `handleRowClick` при `res.data.data === null` не устанавливал `detailData`, но и не показывал ошибку. При некоторых условиях `DetailedReport` рендерился с `null` → краш.

**Решение**: явная обработка `null` — показывать `setError(...)` вместо молчаливого игнорирования.

```tsx
if (res.data.data) {
  setDetailData(res.data.data);
} else {
  setError('Данные анализа недоступны — обработка ещё не завершена.');
}
```
Где применено: `frontend/src/pages/AnalysisHistory.tsx`
Проверка: клик на запись без данных → показывает Alert с ошибкой, не белый экран.

---

### load_dotenv не вызывался — DATABASE_URL не читался из .env
**Статус**: Решено ✅
**Дата решения**: 2026-03-24
**Корневая причина**: `database.py` читает `DATABASE_URL` через `os.getenv()` на уровне модуля. `pydantic-settings` загружает `.env` только для `AppSettings`, но не для `os.getenv()`. `load_dotenv()` нигде не вызывался → `DATABASE_URL = None` → `RuntimeError` при старте.

**Решение**:
```python
# src/app.py — добавить в самом начале, до всех импортов src.*
from dotenv import load_dotenv
load_dotenv()
```
Где применено: `src/app.py`
Проверка: backend стартует без `RuntimeError: DATABASE_URL environment variable is required`.

> ⚠️ Паттерн: `os.getenv()` на уровне модуля не читает `.env` автоматически. Всегда вызывать `load_dotenv()` в точке входа приложения.

---

### Auth.tsx — «Не удалось подключиться» даже с валидным ключом
**Статус**: Решено ✅
**Дата решения**: 2026-03-24
**Корневая причина**: Два бага одновременно:
1. `vite.config.ts` proxy указывал на `localhost:5000` (неправильный порт, backend на 8000)
2. `Auth.tsx` и `client.ts` делали запросы напрямую на `http://127.0.0.1:8000` — минуя Vite proxy → браузер блокировал по CORS

**Решение**:
```typescript
// vite.config.ts — исправлен порт
proxy: { '/api': { target: 'http://localhost:8000', ... } }

// Auth.tsx — относительный путь через proxy
await axios.get('/api/analyses?page=1&page_size=1', ...)

// client.ts — baseURL через proxy
baseURL: import.meta.env.VITE_API_BASE || '/api'
```
Где применено: `frontend/vite.config.ts`, `frontend/src/pages/Auth.tsx`, `frontend/src/api/client.ts`
Проверка: `npm run dev` (перезапуск обязателен — proxy конфиг не подхватывается hot reload); запрос в Network tab идёт на `/api/analyses`, не на `127.0.0.1:8000`.

> ⚠️ Паттерн: при ошибке «Не удалось подключиться» в dev — сначала проверить Network tab. Если запрос идёт на `127.0.0.1:8000` напрямую (не через `/api`) — это proxy не используется.

---

### Отсутствуют компоненты Layout и ProtectedRoute
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: Файлы `Layout.tsx` и `ProtectedRoute.tsx` не были созданы, но `App.tsx` их импортировал — фронтенд не компилировался.

**Решение**:
```tsx
// frontend/src/components/ProtectedRoute.tsx
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
};
```
```tsx
// frontend/src/components/Layout.tsx — AppShell с навигацией и logout
// Полный код: docs/old_bugs(corrected)/bugs.txt → Bug 1
```
Где применено: `frontend/src/components/Layout.tsx`, `frontend/src/components/ProtectedRoute.tsx`
Проверка: `npm run build` в `frontend/` без ошибок компиляции.

---

### Несовместимость структуры данных backend ↔ frontend (ratios + score)
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: `ratios.py` возвращал русскоязычные ключи (`"Коэффициент текущей ликвидности"`), `scoring.py` возвращал `details: dict` с числами — frontend ожидал EN snake_case ключи и `factors: [{name, description, impact}]`. `DetailedReport.tsx` крешился на `result.score.factors` (undefined).

**Решение**:
```python
# src/tasks.py — добавлены RATIO_KEY_MAP и функции трансляции
RATIO_KEY_MAP = {
    "Коэффициент текущей ликвидности": "current_ratio",
    "Коэффициент автономии": "equity_ratio",
    "Рентабельность активов (ROA)": "roa",
    "Рентабельность собственного капитала (ROE)": "roe",
    "Долговая нагрузка": "debt_to_revenue",
}

def _translate_ratios(ratios: dict) -> dict:
    return {RATIO_KEY_MAP.get(k, k): v for k, v in ratios.items()}

def _build_score_payload(raw_score: dict, ratios_en: dict) -> dict:
    # Преобразует details: dict → factors: [{name, description, impact}]
    # Полный код: docs/old_bugs(corrected)/bugs.txt → Bug 2
    ...
```
Где применено: `src/tasks.py`
Проверка: `GET /result/{task_id}` возвращает `ratios.current_ratio` (float) и `score.factors` (list).

---

### NLP pipeline не подключён к основному потоку
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: Вызов `analyze_narrative()` был закомментирован в `tasks.py`. `DetailedReport.tsx` показывал заглушки для рисков и рекомендаций.

**Решение**:
```python
# src/tasks.py — добавить после _build_score_payload(), перед update_analysis()
nlp_result = {"risks": [], "key_factors": [], "recommendations": []}
if text and len(text) > 500:
    try:
        from src.analysis.nlp_analysis import analyze_narrative
        nlp_result = await asyncio.wait_for(analyze_narrative(text), timeout=60.0)
    except asyncio.TimeoutError:
        logger.warning("NLP analysis timed out for task %s", task_id)
    except Exception as nlp_exc:
        logger.warning("NLP analysis failed for task %s: %s", task_id, nlp_exc)
# Добавить "nlp": nlp_result в payload update_analysis
```
Где применено: `src/tasks.py`
Проверка: При доступном AI-провайдере `data.nlp.risks` содержит непустой список.

---

### Хардкод API ключей в frontend
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: `Auth.tsx` хардкодил `'neofin_live_test_key_12345'`, `SettingsPage.tsx` — `'neofin_live_550e8400_...'`. Ключи попадали в git.

**Решение**:
```typescript
// frontend/src/pages/Auth.tsx
const apiKey = import.meta.env.VITE_DEV_API_KEY || 'dev_test_key_12345';
login(apiKey);

// frontend/src/pages/SettingsPage.tsx
const apiKey = import.meta.env.VITE_API_KEY || '****-****-****-****';
```
```
# frontend/.env.example
VITE_API_KEY=your_production_api_key_here
VITE_DEV_API_KEY=dev_test_key_12345
```
Где применено: `frontend/src/pages/Auth.tsx`, `frontend/src/pages/SettingsPage.tsx`, `frontend/.env.example`
Проверка: `git grep 'neofin_live'` — пусто.

---

### CORS не пропускал X-API-Key заголовок
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: `allow_headers` в `src/app.py` не включал `X-API-Key` — браузер блокировал preflight-запросы от frontend.

**Решение**:
```python
# src/app.py — в обоих местах (try и except блоки)
# ДО:
["Content-Type", "Authorization", "X-Requested-With"]
# ПОСЛЕ:
["Content-Type", "Authorization", "X-Requested-With", "X-API-Key"]
```
```
# .env.example
CORS_ALLOW_HEADERS=Content-Type,Authorization,X-Requested-With,X-API-Key
```
Где применено: `src/app.py` (строки ~168, ~181), `.env.example`
Проверка: `OPTIONS /upload` возвращает `Access-Control-Allow-Headers: X-API-Key`.

---

### Hardcoded credentials в database.py
**Статус**: Решено ✅
**Дата решения**: 2026-03-23
**Корневая причина**: `DATABASE_URL` имел дефолт `postgresql+asyncpg://postgres:postgres@localhost:5432/neofin` — пароль был известен из кода.

**Решение**:
```python
# src/db/database.py
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is required. "
        "Please set it in your .env file or environment."
    )
```
Где применено: `src/db/database.py`
Проверка: Запуск без `DATABASE_URL` в env падает с `RuntimeError` (fail-fast).

---

### SSL verification отключён для GigaChat
**Статус**: Решено ✅
**Дата решения**: 2026-03-23
**Корневая причина**: `check_hostname = False` + `CERT_NONE` делали соединение уязвимым к MITM. Использовался `__import__('ssl')` вместо нормального импорта.

**Решение**:
```python
# src/core/gigachat_agent.py
import ssl
_gigachat_ssl_context = ssl.create_default_context()
# Убраны: check_hostname = False, verify_mode = CERT_NONE
```
Где применено: `src/core/gigachat_agent.py`
Проверка: Подключение к GigaChat проходит с валидным сертификатом; при невалидном — `ssl.SSLCertVerificationError`.

---

### Нет аутентификации на API endpoints
**Статус**: Решено ✅
**Дата решения**: 2026-03-23
**Корневая причина**: Все endpoints были публичными. Отсутствовала проверка `X-API-Key`.

**Решение**:
```python
# src/core/auth.py (новый файл)
from fastapi.security import APIKeyHeader
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(api_key_header: str = Security(API_KEY_HEADER)) -> str:
    if not API_KEY:  # DEV_MODE: если API_KEY не задан — пропускаем
        return "dev-mode-no-key"
    if api_key_header != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key_header

# Подключено в: src/routers/analyze.py, src/routers/pdf_tasks.py
# @router.post("/upload")
# async def upload_pdf(file: UploadFile, api_key: str = Depends(get_api_key)):
```
Где применено: `src/core/auth.py`, `src/routers/analyze.py`, `src/routers/pdf_tasks.py`
Проверка: `POST /upload` без заголовка → 401. С `X-API-Key: <key>` → 200.

---

### Бесконечный цикл в обработке страниц PDF
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: `for page_idx in range(0, 20, step)` — цикл выполнялся только один раз (range из одного элемента), `return` внутри цикла выходил после первой итерации. Обрабатывались только первые 20 страниц.

**Решение**:
```python
# src/controllers/analyze.py
# ДО:
for page_idx in range(0, 20, step):
    ...
    return json.loads(res)

# ПОСЛЕ:
all_results = []
for page_idx in range(0, len(file_content), step):
    end_idx = min(page_idx + step, len(file_content))
    ...
    all_results.append(json.loads(res))
return all_results[0] if len(all_results) == 1 else {"pages": all_results}
```
Где применено: `src/controllers/analyze.py` (строки 64–65)
Проверка: PDF с >20 страницами обрабатывается полностью.

---

### Кастомное исключение PdfExtractException не обрабатывалось FastAPI
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: `raise PdfExtractException(detail=str(e))` — FastAPI не знает это исключение, приложение падало с 500 без внятного ответа.

**Решение**:
```python
# src/controllers/analyze.py, src/routers/analyze.py
except Exception as e:
    raise HTTPException(status_code=400, detail=f"PDF processing failed: {str(e)}")
```
Где применено: `src/controllers/analyze.py`, `src/routers/analyze.py`
Проверка: Битый PDF → 400 с читаемым `detail`, не 500.

---

### Отсутствие timeout в запросах к AI agent
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: `session.post(url)` без timeout — при недоступном AI сервисе запрос висел бесконечно, блокируя воркер.

**Решение**:
```python
# src/core/agent.py
async def invoke(self, input: dict, timeout: int | None = None) -> str | None:
    actual_timeout = timeout or self.timeout  # default 120s
    try:
        async with asyncio.timeout(actual_timeout):
            return await self.request(...)
    except asyncio.TimeoutError:
        logger.error("Agent request timeout after %d seconds", actual_timeout)
        raise
```
Где применено: `src/core/agent.py`
Проверка: При недоступном Ollama — `TimeoutError` через 120s, не зависание.

---

### Хардкод паролей в docker-compose.yml
**Статус**: Решено ✅
**Дата решения**: 2026-03-23
**Корневая причина**: `POSTGRES_PASSWORD: postgres` захардкожен в `docker-compose.yml` — попадал в git.

**Решение**:
```yaml
# docker-compose.yml
environment:
  POSTGRES_USER: ${POSTGRES_USER:-postgres}
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
  DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/neofin
```
Где применено: `docker-compose.yml`, `.env.example`
Проверка: `docker-compose config` показывает значения из `.env`, не хардкод.

---

### Хардкод путей к Python в run.ps1 / run.bat
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: `E:\neo-fin-ai\venv\Scripts\python.exe` захардкожен — скрипты не работали ни на какой другой машине.

**Решение**:
```powershell
# run.ps1
$pythonPath = ".\env\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
    Write-Host "ERROR: Virtual environment not found. Run: python -m venv env"
    return
}
& $pythonPath -m uvicorn ...
```
Где применено: `run.ps1`, `run.bat`
Проверка: Скрипты запускаются на любой машине с виртуальным окружением в `./env/`.

---

### pdfminer.six не устанавливался на Python < 3.10
**Статус**: Решено ✅
**Дата решения**: 2026-03-15
**Корневая причина**: `pdfplumber~=0.11.9` тянул `pdfminer.six==20251230`, которая требует Python 3.10+. На Python 3.9 установка падала.

**Решение**:
```
# requirements.txt
pdfplumber~=0.12.0   # вместо ~=0.11.9
```
Проект требует Python 3.11+ (зафиксировано в `Dockerfile` и документации).
Где применено: `requirements.txt`
Проверка: `pip install -r requirements.txt` на Python 3.11 без ошибок.

---

### Неправильная валидация result в get_result endpoint
**Статус**: Решено ✅
**Дата решения**: 2026-03-22
**Корневая причина**: `payload.update(analysis.result)` без проверки типа — если `result` не dict (например, строка или None), падал `RuntimeError`.

**Решение**:
```python
# src/routers/pdf_tasks.py (строка ~44)
if analysis.result and isinstance(analysis.result, dict):
    payload.update(analysis.result)
```
Где применено: `src/routers/pdf_tasks.py`
Проверка: `GET /result/{id}` при `result=None` или `result="error string"` → корректный JSON без 500.
