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

## Smoke tier (`manifest.json`)

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

Почему так:

- Camelot на реальных annual reports может работать десятки секунд
- часть документов может стабильно проходить только через `stream`
- heavy-tier должен проверять узкие business-инварианты, а не пытаться валидировать весь metrics dict

## OCR cases

Формат `manifest_heavy.json` уже допускает `pipeline = "force_ocr"`, но committed scanned real-PDF fixtures пока не добавлены. Когда появится curated scanned corpus, он должен входить только в этот optional heavy layer, а не в default smoke path.
