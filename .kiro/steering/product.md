# NeoFin AI — Product Overview

NeoFin AI is a hybrid AI platform for financial analysis of enterprises. It extracts financial data from PDF reports (including scanned documents via OCR), calculates 13 financial ratios across 4 groups, produces an integral score (0–100), and generates NLP-based recommendations through language models.

## Core Value Proposition

The system doesn't just calculate ratios — it **explains the origin of every number**, from raw PDF to final score. Each extracted metric carries a Confidence Score indicating how reliable the extraction was.

## Key Capabilities

- PDF processing: text extraction (PyPDF2), table extraction (camelot/pdfplumber), OCR fallback (pytesseract) for scanned documents
- Smart PDF detection: analyzes first 3 pages for `/Image` objects to decide extraction method
- 13 financial ratios in 4 groups: liquidity, profitability, financial stability, business activity
- Integral scoring 0–100 with risk level, contributing factors, and normalized scores
- Confidence Score per metric: `table_exact` (0.9) → `table_partial` (0.7) → `text_regex` (0.5) → `derived` (0.3)
- Metrics below `CONFIDENCE_THRESHOLD` (default 0.5) are excluded from ratio calculations
- NLP analysis: risk identification, key factors, 3–5 recommendations via LLM
- Multi-period analysis: up to 5 reporting periods per session with trend visualization
- Real-time WebSocket updates during analysis pipeline phases
- Demo mode: numeric data masking via `DEMO_MODE=1`

## Hybrid Architecture

Two independent levels — LLM unavailability never affects the numeric result:
- **Level 1 (deterministic)**: extraction → confidence filtering → ratios → scoring. Always runs.
- **Level 2 (probabilistic)**: NLP analysis via GigaChat / DeepSeek (HuggingFace) / Ollama. Optional, gracefully degrades to empty lists on failure.

## AI Provider Selection (at startup, not runtime)

```
GIGACHAT_CLIENT_ID set? → GigaChat (OAuth2, token cache 55 min)
HF_TOKEN set?           → DeepSeek via HuggingFace
LLM_URL set?            → Ollama (fully offline)
None set?               → NLP disabled, numeric analysis continues
```

## Target Context

Competition project "Молодой финансист 2026". Russian-language domain (financial terms, UI labels, and some internal keys are in Russian).
