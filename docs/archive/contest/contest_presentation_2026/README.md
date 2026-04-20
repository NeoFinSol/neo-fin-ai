# Конкурсная презентация NeoFin AI

В этой папке лежит актуальная конкурсная колода для `Молодой Финансист 2026`, собранная в режиме `PPTX-first` на `PptxGenJS`.

## Что здесь находится

- `neo-fin-ai-molodoy-finansist-2026.cjs` — основной entrypoint сборки
- `neo-fin-ai-molodoy-finansist-2026.pptx` — готовый PowerPoint-файл
- `build-log.txt` — лог последней сборки
- `src/theme.js` — тема, цвета, типографика и общие layout-helper'ы
- `src/renderers.js` — мастер-шаблоны и рендереры слайдов
- `src/content.js` — весь контент колоды и единая точка редактирования контактов
- `pptxgenjs_helpers/` — локальная копия helper-модулей для валидации layout

## Архитектура колоды

- `1–15` — `main story`
- `16–32` — `backup / Q&A`
- `33` — отдельный финальный слайд `Спасибо за внимание`

Колода сознательно разделена на два режима:

- основная история для защиты и уверенного narrative flow
- backup-блок для ответов на вопросы жюри по контрактам, runtime, метрикам, рискам и бизнес-модели

## Где менять контакты и автора

Редактировать только здесь:

- [content.js](src/content.js)

Блок:

```js
const CONTACT = {
  author: "[Ваше имя]",
  email: "email@example.com",
  telegram: "@telegram",
  github: "github.com/NeoFinSol/neo-fin-ai",
};
```

Эти значения автоматически подставляются в backup-слайд с контактами.

## Как собрать

```powershell
cd docs/archive/contest/contest_presentation_2026
npm install
node .\neo-fin-ai-molodoy-finansist-2026.cjs
```

После сборки обновляются:

- `neo-fin-ai-molodoy-finansist-2026.pptx`
- `build-log.txt`

## Что проверять вручную перед защитой

В этой среде нет полноценного desktop-render smoke-check, поэтому финальная проверка делается в два слоя:

1. Автоматически

- сборка проходит без ошибок
- `build-log.txt` не содержит overlap/out-of-bounds warnings
- в `.pptx` ровно `33` слайда

2. Вручную в PowerPoint

- титульный слайд выглядит как сильное вступление, а не как титульный формализм
- `16–32` визуально читаются как backup, а не как продолжение main-story
- последний слайд содержит только `Спасибо за внимание`
- нет странных переносов в заголовках и карточках
- контакты и имя автора подставлены корректно

## На что опирается контент

Колода выровнена по фактическому состоянию проекта и не должна возвращаться к спекулятивным тезисам про трейдинг-сигналы или рыночные прогнозы, которых нет в продукте.

Основные источники:

- `docs/ARCHITECTURE.md`
- `docs/API.md`
- `docs/CONFIGURATION.md`
- `docs/ROADMAP.md`
- `frontend/src/api/interfaces.ts`
- `docs/archive/contest/CONTEST_DEMO_RUNBOOK.md`
- `docs/archive/contest/CONTEST_OPERATOR_CARD.md`
- `tests/data/demo_manifest.json`

Стратегическая продуктовая рамка и прочие внутренние материалы не публикуются в открытом GitHub-репозитории; при обновлении колоды опираться на актуальное публичное ядро `docs/*` и локальный контур владельца.

## Дизайн-направление

- тёмная `premium fintech`-сцена
- `Bahnschrift` для заголовков
- `Segoe UI` для основного текста
- `Cascadia Code` для справочных кодовых блоков
- 4 базовых паттерна: `hero`, `split`, `contrast`, `reference`
