# Интерфейс НеоФин.Документы

Этот модуль реализует пользовательский интерфейс `НеоФин.Документы` — первого сервиса экосистемы `НеоФин.Контур`.

## 1. Что делает интерфейс

Интерфейс отвечает за:

- загрузку PDF-отчётов;
- выбор AI-провайдера перед анализом;
- отображение статусов выполнения;
- показ отчёта с метриками, коэффициентами, скорингом и методикой;
- историю анализов;
- многопериодные сценарии;
- правдивое отображение состояния AI-контурa.

## 2. Основные страницы

### Главная

Файл: `src/pages/Dashboard.tsx`

Показывает:

- бренд `НеоФин.Документы`;
- пояснение, что это модуль экосистемы `НеоФин.Контур`;
- drag-and-drop загрузку PDF;
- selector AI-провайдера;
- прогресс этапов анализа;
- быстрый переход к итоговому отчёту.

По умолчанию интерфейс предпочитает `Ollama`, если backend сообщает, что он доступен через `/system/ai/providers`.

### Детальный отчёт

Файл: `src/pages/DetailedReport.tsx`

Показывает:

- набор метрик;
- коэффициенты;
- итоговый скоринг;
- badges benchmark’ов и period-basis;
- блок `Как рассчитано`;
- AI-инсайты или честный deterministic fallback-текст.

### История анализов

Файл: `src/pages/AnalysisHistory.tsx`

Показывает список анализов, их статус, итоговый score и быстрый доступ к сохранённым отчётам.

### Настройки

Файл: `src/pages/SettingsPage.tsx`

Содержит настройки профиля и эксплуатационные элементы интерфейса. Layout синхронизирован с текущими spacing-правками и рассчитан на desktop/tablet ширину без “съехавших” кнопок.

### Авторизация и служебные страницы

- `src/pages/Auth.tsx`
- `src/pages/NotFound.tsx`

Обе страницы уже приведены к текущему бренду и legal-copy 2026 года.

## 3. Truthful AI-state

Интерфейс не делает вывод о наличии AI только по содержимому `nlp`.

Источник правды — `ai_runtime`:

- `requested_provider`
- `effective_provider`
- `status`
- `reason_code`

В зависимости от `ai_runtime.status` интерфейс показывает:

- полноценный AI-блок;
- deterministic fallback;
- сообщение о пустом ответе модели;
- сообщение о provider error;
- сценарий `skipped`, если AI-контур не использовался.

Это исключает ложные сообщения вида “AI недоступен”, если фактически задача завершилась иначе.

## 4. Explainable scoring в интерфейсе

`ScoreInsightsCard` и связанные компоненты показывают не только score, но и методику:

- `benchmark_profile`
- `period_basis`
- `guardrails`
- `leverage_basis`
- `ifrs16_adjusted`
- `adjustments`
- `peer_context`

Это позволяет объяснить:

- почему выбран retail-aware benchmark;
- почему для interim-периода применена годовая база;
- почему score был ограничен guardrail’ом;
- какой вариант leverage участвует в расчёте.

## 5. Технический стек

- React 19
- TypeScript
- Mantine 8
- React Router 7
- Axios
- Motion
- `@tabler/icons-react`
- `lucide-react`

Графический стек остаётся совместимым с `@mantine/charts`, поэтому `recharts` не удаляется из зависимостей.

## 6. Контракт данных

Единственный источник правды для клиентских типов:

- `src/api/interfaces.ts`

Особенно важные структуры:

- `AnalysisData`
- `ScoreData`
- `ScoringMethodology`
- `AIRuntimeInfo`
- `FinancialRatios`
- `FinancialMetrics`

`src/api/types.ts` не используется как канонический контракт.

## 7. Тесты и baseline

Актуальный интерфейсный baseline:

- `96` тестов;
- `96 passed`;
- покрытие:
  - `65.05% lines`
  - `63.99% statements`
  - `68.88% functions`
  - `53.21% branches`

## 8. Полезные команды

```bash
npm --prefix frontend install
npm --prefix frontend run dev
npm --prefix frontend run test
npm --prefix frontend run coverage
npm --prefix frontend run lint
```

## 9. Что важно не ломать

- русскоязычный брендинг `НеоФин.Документы`;
- selector AI-провайдера на главной;
- truthful rendering через `ai_runtime`;
- badges benchmark’ов и блок `Как рассчитано`;
- legal-copy: `НеоФин. Все права защищены, 2026.`
