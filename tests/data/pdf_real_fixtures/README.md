# Real PDF Smoke Fixtures

Этот набор хранит маленький committed baseline corpus из реальных PDF-файлов финансовой отчётности.

## Зачем он нужен

- synthetic dataset в `tests/data/pdf_regression_corpus.json` хорошо покрывает layout-driven edge cases
- real PDFs дополнительно страхуют text-layer extraction на настоящих годовых отчётах
- baseline pack должен оставаться быстрым и стабильным в CI

## Что здесь лежит

- `manifest.json` — metadata, provenance, `sha256`, expected subset metric values и expected extraction sources
- `*.pdf` — committed smoke fixtures

## Почему pipeline сейчас `text_only`

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

Следующий слой — optional heavy corpus с full pipeline / OCR cases.
