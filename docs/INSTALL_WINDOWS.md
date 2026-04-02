# Установка НеоФин.Документы на Windows

Документ описывает два рабочих сценария:

1. быстрый запуск через Docker Compose;
2. локальный запуск без Docker с OCR-цепочкой и опциональным Ollama.

## 1. Что понадобится

### Обязательные инструменты

- Windows 10/11 x64
- Python 3.11
- Node.js 20+
- Git

### Для Docker-сценария

- Docker Desktop

### Для локального OCR-сценария

- Ghostscript
- Tesseract OCR с русским языковым пакетом
- Poppler for Windows

### Для локального AI-контура

- Ollama для Windows

## 2. Официальные страницы загрузки

При обновлении этой инструкции ориентируйтесь на официальные страницы проектов:

- Ghostscript: [официальная страница загрузок](https://ghostscript.com/releases/gsdnld.html)
- Tesseract for Windows: [UB Mannheim installer wiki](https://github.com/UB-Mannheim/tesseract/wiki)
- Poppler for Windows: [oschwartz10612/poppler-windows releases](https://github.com/oschwartz10612/poppler-windows/releases)
- Ollama: [официальная загрузка для Windows](https://ollama.com/download/windows)

## 3. Вариант A — быстрый старт через Docker

### Шаг 1. Клонировать проект

```powershell
git clone <repo-url>
cd E:\neo-fin-ai
```

### Шаг 2. Создать `.env`

```powershell
Copy-Item .env.example .env
```

Минимально заполните:

- `API_KEY`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`

Рекомендуемый базовый режим:

```env
SCORING_PROFILE=auto
TASK_RUNTIME=background
```

### Шаг 3. Запустить стек

```powershell
docker compose up -d --build
```

### Шаг 4. Проверить сервис

- интерфейс: `http://127.0.0.1/`
- API: `http://127.0.0.1/api/system/health`

## 4. Вариант B — локальный запуск без Docker

### Шаг 1. Подготовить Python-окружение

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
```

### Шаг 2. Подготовить интерфейс

```powershell
npm --prefix frontend install
```

### Шаг 3. Установить OCR-зависимости

#### Ghostscript

- Установите актуальный stable release с официальной страницы.
- После установки добавьте каталог `bin` в `PATH`.

Проверка:

```powershell
gswin64c --version
```

#### Tesseract OCR

- Используйте Windows-инсталлятор из репозитория UB Mannheim.
- Во время установки обязательно включите русский язык (`rus`).
- Добавьте каталог Tesseract в `PATH`.

Проверка:

```powershell
tesseract --version
tesseract --list-langs
```

В выводе должен присутствовать `rus`.

#### Poppler

- Скачайте актуальный Windows release.
- Распакуйте его в удобный каталог, например `C:\Tools\poppler`.
- Добавьте `Library\bin` в `PATH`.

Проверка:

```powershell
pdfinfo -v
```

## 5. Локальный AI-контур через Ollama

Если вы хотите использовать локальную языковую модель без внешних API:

1. Установите Ollama.
2. Загрузите модель:

```powershell
ollama pull qwen3.5:9b
```

3. В `.env` задайте:

```env
LLM_URL=http://localhost:11434/api/generate
LLM_MODEL=qwen3.5:9b
```

Примечание:

- кодовый дефолт `LLM_MODEL` в проекте остаётся другим;
- для JSON-heavy сценариев `qwen3.5:9b` является рекомендуемым локальным профилем.

## 6. Настройка `.env` для локального запуска

Минимальный пример:

```env
API_KEY=dev-key-123
DEV_MODE=1
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/neofin
SCORING_PROFILE=auto
TASK_RUNTIME=background
LLM_URL=http://localhost:11434/api/generate
LLM_MODEL=qwen3.5:9b
```

Если Ollama не нужен, `LLM_*` можно не задавать.

## 7. Запуск сервисов без Docker

### Backend

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn src.app:app --host 0.0.0.0 --port 8000
```

### Интерфейс

```powershell
npm --prefix frontend run dev
```

## 8. Быстрая проверка

### Проверка backend

```powershell
curl http://127.0.0.1:8000/system/health
```

### Проверка интерфейса

Откройте:

- `http://127.0.0.1:3000` для dev-сервера интерфейса;
- `http://127.0.0.1/` при Docker Compose.

### Проверка локального AI

```powershell
ollama list
```

## 9. Практические замечания

- для правдивого demo/scoring-контура держите `SCORING_PROFILE=auto`;
- для локального demo без внешних токенов выбирайте в интерфейсе `Ollama`, если провайдер доступен;
- при проблемах с OCR первым делом проверьте `PATH` для Ghostscript, Tesseract и Poppler;
- если нужен стабильный длительный runtime, переходите с `background` на `celery`.

## 10. Связанные документы

- [README](/E:/neo-fin-ai/README.md)
- [CONFIGURATION](/E:/neo-fin-ai/docs/CONFIGURATION.md)
- [API](/E:/neo-fin-ai/docs/API.md)
