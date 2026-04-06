# Real PDF Fixtures

Этот каталог хранит committed corpus из реальных PDF-файлов финансовой отчётности.

## Зачем он нужен

- synthetic dataset в `tests/data/pdf_regression_corpus.json` хорошо покрывает layout-driven edge cases
- real PDFs дополнительно страхуют text-layer extraction на настоящих годовых отчётах
- baseline smoke pack должен оставаться быстрым и стабильным в CI
- optional heavy tier нужен для явной проверки full pipeline на реальных annual reports

## Что здесь лежит

- `manifest.json` — metadata, provenance, `sha256`, expected subset metric values и expected extraction sources
- `manifest_heavy.json` — отдельный manifest для optional heavy-tier с full pipeline
- `*.pdf` — committed smoke fixtures

`sha256` здесь хранится не “для справки”, а как часть fixture identity:

- hash используется как invariant against silent fixture substitution;
- calibration harness и smoke tests должны доверять только manifest-backed `filename + sha256`, а не старым локальным путям.

## Smoke tier (`manifest.json`)

`manifest.json` теперь может содержать два `kind`:

- `smoke`
- `calibration_anchor`

Default smoke loader обязан брать только `kind == "smoke"`.

`kind == "calibration_anchor"` означает:

- fixture committed и доступен calibration harness через `fixture_ref`;
- fixture не попадает в default smoke path;
- fixture существует для gated calibration coverage, а не для расширения fast CI cardinality.

Для первой итерации smoke pack intentionally использует:

- `is_scanned_pdf()`
- `extract_text()`
- `parse_financial_statements_with_metadata([], text)`

а не full Camelot pipeline для каждого файла.

Причина простая: на реальных annual reports table extraction может занимать десятки секунд и быть чувствительной к layout/runtime noise. Это плохо подходит для fast green path.

Synthetic corpus уже страхует:

- note columns
- year columns
- RSBU line codes
- garbled labels
- OCR pseudo-tables

## Heavy tier (`manifest_heavy.json`)

Отдельный optional слой использует:

- `extract_text()`
- `extract_tables()`
- `parse_financial_statements_with_metadata(tables, text)`

Он не должен входить в обычный быстрый прогон. Heavy-tier запускается только явно:

```powershell
$env:RUN_PDF_REAL_HEAVY = "1"
python -m pytest tests/test_pdf_real_heavy_fixtures.py -q
```

или через pytest option:

```powershell
python -m pytest tests/test_pdf_real_heavy_fixtures.py -q --run-pdf-real-heavy
```

Почему так:

- Camelot на реальных annual reports может работать десятки секунд
- часть документов может стабильно проходить только через `stream`
- heavy-tier должен проверять узкие business-инварианты, а не пытаться валидировать весь metrics dict

### Рекомендация для CI

- default CI path heavy-tier не запускает
- heavy-tier лучше держать в отдельном nightly / integration job
- если corpus временно отсутствует или manifest повреждён, suite должен cleanly skip, а не ломать обычный pytest collection

## OCR cases

Формат `manifest_heavy.json` уже допускает `pipeline = "force_ocr"`, но committed scanned real-PDF fixtures пока не добавлены. Когда появится curated scanned corpus, он должен входить только в этот optional heavy layer, а не в default smoke path.

Для calibration harness действует отдельный более жёсткий contract:

- `force_ocr` — OCR-only execution mode for calibration, not a document classification;
- `force_ocr` intentionally disables table extraction;
- в calibration wave это всегда `extract_text_from_scanned(pdf)` + `tables = []`.

Committed Russian fixtures в этой волне могут жить в `manifest.json` как `calibration_anchor`, не попадая в default smoke tier.
