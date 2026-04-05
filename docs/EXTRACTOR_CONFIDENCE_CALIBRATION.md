# Extractor Confidence Calibration Wave

## Контекст

Эта волна реализована как `Internal-First+` для extractor confidence policy:

- public V2 wire shape не меняется;
- frontend contract не меняется;
- default `CONFIDENCE_THRESHOLD=0.5` не меняется;
- меняется только extractor-side runtime calibration policy и внутренний evaluation tooling.

Primary objective этой волны: улучшить `operational trust` на явной decision surface:

- threshold decision;
- winner decision;
- merge / replacement decision;
- false-positive absence decision.

## Что изменилось

В runtime введён единый declarative-first policy layer в [confidence_policy.py](/E:/neo-fin-ai/src/analysis/extractor/confidence_policy.py).

Policy теперь является single source of truth для:

- profile baselines;
- quality bands;
- structural bonus;
- guardrail penalty;
- conflict penalty;
- strong direct threshold.

Внутри extractor добавлен отдельный calibration harness:

- [calibration.py](/E:/neo-fin-ai/src/analysis/extractor/calibration.py)
- [run_extractor_confidence_calibration.py](/E:/neo-fin-ai/scripts/run_extractor_confidence_calibration.py)
- [extractor_confidence_calibration.json](/E:/neo-fin-ai/tests/data/extractor_confidence_calibration.json)

Также убраны дублирующиеся runtime reads threshold-конфига: `tasks.py` и legacy extractor helpers теперь берут `CONFIDENCE_THRESHOLD` из `app_settings`, а не парсят env по отдельности.

## Runtime calibration decision

После offline calibration и review evidence pack landed policy:

- усиливает `text/code_match/direct` и соседние text-direct profiles;
- заметно ужесточает weak OCR direct profiles;
- немного ужесточает weak keyword evidence;
- усиливает penalties для weak-quality, conflicts и guardrail-adjusted states;
- сохраняет `issuer_fallback` и `strong_direct_threshold` без semantic drift.

Итоговый runtime policy зафиксирован как:

- `RUNTIME_CONFIDENCE_POLICY = CALIBRATED_RUNTIME_CONFIDENCE_POLICY`

## Почему policy принята

Evidence pack в [EXTRACTOR_CONFIDENCE_CALIBRATION_EVIDENCE.md](/E:/neo-fin-ai/docs/EXTRACTOR_CONFIDENCE_CALIBRATION_EVIDENCE.md) показывает:

- baseline operational accuracy: `0.667`
- calibrated operational accuracy: `1.000`
- false accepts: `2 -> 0`
- false rejects: `0 -> 0`
- survivors: `5 -> 3`
- boundary density: `0.333 -> 0.333`
- threshold sweep показывает лучший operational outcome именно на runtime threshold `0.50`

Важно:

- survivor coverage действительно стала уже, но improvement не достигнут за счёт collapse в ноль;
- calibrated policy сохраняет три корректных survivor path и убирает два ложных survive;
- source-critical parse case для table keyword path сохранён;
- merge-sensitive case `llm_replaces_weak_text_keyword_fallback` исправлен в пользу правильного operational outcome.

## Что сознательно НЕ менялось

- public extractor metadata contract;
- frontend explainability rendering;
- consumer-policy redesign;
- online/self-adjusting calibration;
- adaptive runtime thresholding;
- любые hidden runtime toggles для shadow policy.

Shadow consumer semantics остаются strictly offline-only:

- не импортируются в production decision path;
- не влияют на persisted outputs;
- используются только в reports и future design exploration.

## Ограничения и наблюдения

- На текущем frozen labeled corpus `ECE` не улучшился (`0.317 -> 0.414`), хотя `Brier score` улучшился (`0.315 -> 0.278`) и operational decision quality выросла до `1.000`.
- Это допустимо для этой волны, потому что primary objective здесь — operational trust, а не generic score aesthetics.
- Из-за малого calibration corpus `ECE` сейчас нужно трактовать как diagnostic signal, а не как самостоятельный ship/no-ship gate.

Следующий логичный шаг после этой волны:

- расширить labeled corpus;
- добавить больше merge-sensitive и expected-absent cases;
- повторно проверить reliability metrics на более широком наборе.

## Артефакты волны

- Human-readable evidence pack: [EXTRACTOR_CONFIDENCE_CALIBRATION_EVIDENCE.md](/E:/neo-fin-ai/docs/EXTRACTOR_CONFIDENCE_CALIBRATION_EVIDENCE.md)
- Machine-readable evidence pack: [EXTRACTOR_CONFIDENCE_CALIBRATION_EVIDENCE.json](/E:/neo-fin-ai/docs/EXTRACTOR_CONFIDENCE_CALIBRATION_EVIDENCE.json)
- Frozen calibration manifest: [extractor_confidence_calibration.json](/E:/neo-fin-ai/tests/data/extractor_confidence_calibration.json)
- Harness entrypoint: [run_extractor_confidence_calibration.py](/E:/neo-fin-ai/scripts/run_extractor_confidence_calibration.py)

## Как перепроверить локально

```powershell
python scripts/run_extractor_confidence_calibration.py --format markdown
python scripts/run_extractor_confidence_calibration.py --format json
python -m pytest tests/test_extractor_confidence_calibration.py -q
```
