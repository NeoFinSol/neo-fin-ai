# PeriodInput Audit Report

## Summary
- **Total occurrences found:** 8 (across 4 files)
- **Require update:** 4 (direct instantiations without `file_path`)
- **Already have file_path:** 0
- **Unclear/needs review:** 1 (duck-typed usage in `tasks.py`)

---

## Detailed Findings

### File: `src/models/schemas.py`
| Line | Code | Category | Action Required |
|------|------|----------|-----------------|
| 93 | `class PeriodInput(BaseModel):` | D | **Add `file_path: str` field** — this is the definition itself |
| 114 | `periods: list[PeriodInput] = Field(min_length=1, max_length=5)` | D | No change needed — type annotation only |

---

### File: `src/routers/multi_analysis.py`
| Line | Code | Category | Action Required |
|------|------|----------|-----------------|
| (no direct instantiation) | Router accepts `MultiAnalysisRequest` (JSON body) which contains `list[PeriodInput]` | D | **Requires full rewrite** — change from JSON body to `multipart/form-data`; create `PeriodInput(period_label=label, file_path=tmp.name)` for each uploaded file |

> Note: Currently the router passes `body.periods` (list of `PeriodInput` from JSON) directly to `process_multi_analysis`. After the fix, it must save each uploaded file to a temp path and construct `PeriodInput(period_label=label, file_path=tmp.name)`.

---

### File: `src/tasks.py`
| Line | Code | Category | Action Required |
|------|------|----------|-----------------|
| 544 | `periods: list,  # list[PeriodInput] — avoid circular import; duck-typed` | D | **Review** — duck-typed, no direct instantiation. After fix, `period.file_path` must be accessible. The comment already documents the expected `.file_path` attribute. |
| 554 | `periods: List of PeriodInput objects with .period_label and .file_path attributes` | D | Documentation only — no code change needed here |
| ~590 | `file_path: str = period.file_path` (implicit access in loop) | D | **Requires update** — `_process_single_period` call must pass `period.file_path` correctly; add `FileNotFoundError` handling |

---

### File: `tests/test_qwen_regression_exploratory.py`
| Line | Code | Category | Action Required |
|------|------|----------|-----------------|
| 64 | `from src.models.schemas import PeriodInput` | C | Import only — no change needed |
| 68 | `instance = PeriodInput(period_label="2023")` | C | **Add `file_path`** after fix — currently tests the bug (no `file_path`). After task 5.1, this test will need updating OR the test is intentionally checking the old behavior (bug exploration test — leave as-is until task 5.3) |

> Note: This is a **bug exploration test** — it intentionally creates `PeriodInput` without `file_path` to confirm the bug. After the fix (task 5.1), `PeriodInput(period_label="2023")` will raise a `ValidationError` (missing required field), so the test will need to be updated in task 5.3.

---

### File: `tests/test_multi_analysis_router.py`
| Line | Code | Category | Action Required |
|------|------|----------|-----------------|
| 281 | `from src.models.schemas import PeriodInput, MultiAnalysisRequest` | C | Import only — no change needed |
| 286 | `PeriodInput(period_label=label_text)` | C | **Add `file_path`** — after fix, this will raise `ValidationError` without `file_path`. Update to `PeriodInput(period_label=label_text, file_path="/tmp/test.pdf")` |
| 290 | `PeriodInput(period_label=label_text)` | C | **Add `file_path`** — same as above |

---

## All Direct Instantiations Summary

| # | File | Line | Code | Has `file_path`? | Category | Action |
|---|------|------|------|-----------------|----------|--------|
| 1 | `tests/test_qwen_regression_exploratory.py` | 68 | `PeriodInput(period_label="2023")` | ❌ No | C | Leave as-is until task 5.3 (bug exploration test) |
| 2 | `tests/test_multi_analysis_router.py` | 286 | `PeriodInput(period_label=label_text)` | ❌ No | C | Add `file_path="/tmp/test.pdf"` |
| 3 | `tests/test_multi_analysis_router.py` | 290 | `PeriodInput(period_label=label_text)` | ❌ No | C | Add `file_path="/tmp/test.pdf"` |
| 4 | `src/routers/multi_analysis.py` | (implicit via JSON body) | `MultiAnalysisRequest` deserialization | ❌ No | D | Rewrite to multipart/form-data, construct `PeriodInput(period_label=label, file_path=tmp.name)` |

---

## Recommendations

1. **Task 5.1 first**: Add `file_path: str` to `PeriodInput` in `src/models/schemas.py`. This is the root fix.

2. **Task 5.2 next**: Rewrite `src/routers/multi_analysis.py` to accept `multipart/form-data` instead of JSON body. For each uploaded file, save to `tempfile.NamedTemporaryFile` and construct `PeriodInput(period_label=label, file_path=tmp.name)`.

3. **Task 5.2.1**: Update `src/tasks.py` `process_multi_analysis` to pass `period.file_path` to `_process_single_period` and add `FileNotFoundError` handling.

4. **Update test_multi_analysis_router.py** (lines 286, 290): After task 5.1, the property-based test `test_property_6_period_label_length` will break because `PeriodInput(period_label=label_text)` will fail with `ValidationError` (missing `file_path`). Update to `PeriodInput(period_label=label_text, file_path="/tmp/test.pdf")`.

5. **Leave `test_qwen_regression_exploratory.py` line 68 unchanged** until task 5.3 — it is intentionally testing the bug condition.

---

## Blockers

- [ ] None — all occurrences are identified and categorized. Tasks 5.1 → 5.2 → 5.2.1 can proceed in order.

---

## Search Commands Used

```bash
grep -rn "PeriodInput(" src/ --include="*.py"
grep -rn "PeriodInput(" tests/ --include="*.py"
grep -rn "PeriodInput" . --include="*.py" --exclude-dir=".git" --exclude-dir="__pycache__" --exclude-dir=".claude"
```

## Files Scanned

- `src/models/schemas.py` — definition
- `src/routers/multi_analysis.py` — router (implicit instantiation via JSON deserialization)
- `src/tasks.py` — duck-typed usage
- `tests/test_qwen_regression_exploratory.py` — bug exploration test
- `tests/test_multi_analysis_router.py` — property-based tests
