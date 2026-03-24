# Overview — NeoFin AI

## Текущий статус

| Компонент | Статус | Комментарий |
|-----------|--------|-------------|
| Backend (FastAPI) | 🟡 Работает частично | Запускается, принимает запросы, но extraction не работает для реальных PDF |
| Frontend (React/Vite) | 🟡 Работает частично | Запускается, но показывает Score: 0 и только Revenue |
| PDF Extraction | 🔴 Сломан | Не парсит реальные отчёты (Магнит) — только revenue, остальные метрики null |
| Scoring | 🟡 Готов к работе | Исправлен ключ "Долговая нагрузка" → "Финансовый рычаг", но не получает данные |
| AI Service (HuggingFace) | 🟢 Настроен | HF_TOKEN работает, Llama 3.1 8B подключена |
| History (frontend) | 🟢 Реализован | localStorage + контекст, сохраняет при анализе |

## Что работает
- Backend запускается на порту 8001
- Frontend запускается на порту 3000
- API endpoint `/analyze/pdf/file` принимает PDF
- Scoring функция корректно считает score при наличии данных
- History сохраняет результаты в localStorage

## Что НЕ работает (активные баги)
- **PDF extraction не парсит реальные отчёты**: Для Магнита возвращает только revenue, остальные метрики null
- **Frontend показывает Score: 0**: Из-за отсутствия данных extraction
- **AI service не возвращает структурированные данные**: Возвращает текст, а не JSON

## Приоритеты
1. 🔴 Исправить PDF extraction для реальных русских отчётов
2. 🔴 Убедиться что AI service возвращает валидный JSON
3. 🟡 Проверить что frontend корректно отображает данные при наличии

## Ключевые файлы для отладки
- `src/analysis/pdf_extractor.py` — парсинг PDF
- `src/controllers/analyze.py` — fallback regex extraction
- `src/core/ai_service.py` — AI extraction
- `src/analysis/scoring.py` — расчёт score
