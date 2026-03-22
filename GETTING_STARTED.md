# 🎯 Neo Fin AI - Solution Setup Guide

Решение успешно подготовлено для разработки в Visual Studio Community 2026!

## 📋 Что было создано

### ✅ Файлы решения
- **`neo-fin-ai.sln`** — главный файл решения для VS (содержит оба проекта)
- **`Backend.pyproj`** — проект Python для FastAPI backend
- **`frontend/Frontend.csproj`** — проект для React frontend

### ✅ Скрипты быстрого запуска
- **`run.ps1`** — PowerShell скрипт с интерактивным меню
- **`run.bat`** — Batch файл для быстрого запуска
- **`SOLUTION.md`** — документация структуры проекта

## 🚀 Быстрый запуск

### Вариант 1: Через PowerShell (Рекомендуется)

```powershell
# Открыть интерактивное меню
.\run.ps1

# Или выполнить конкретную команду
.\run.ps1 -Command docker-up
```

**Доступные команды:**
```powershell
.\run.ps1 -Command docker-up      # Запустить Docker Compose
.\run.ps1 -Command docker-down    # Остановить Docker Compose
.\run.ps1 -Command logs           # Показать логи backend
.\run.ps1 -Command backend        # Запустить backend локально
.\run.ps1 -Command frontend       # Запустить frontend локально
.\run.ps1 -Command install        # Установить зависимости
.\run.ps1 -Command migrate        # Применить миграции БД
.\run.ps1 -Command clean          # Удалить контейнеры и тома
```

### Вариант 2: Через Batch файл

```cmd
run.bat
```

### Вариант 3: Прямые команды Docker

```powershell
cd E:\neo-fin-ai

# Запустить всё в Docker (рекомендуется)
docker-compose up -d

# Проверить статус
docker-compose ps

# Посмотреть логи
docker-compose logs -f backend
```

## 🌐 Доступы после запуска

| Сервис | URL | Описание |
|--------|-----|---------|
| **Frontend** | http://localhost | React приложение |
| **Backend API** | http://localhost:8000 | FastAPI сервер |
| **API Документация (Swagger)** | http://localhost:8000/docs | Интерактивная документация |
| **API Документация (ReDoc)** | http://localhost:8000/redoc | Альтернативная документация |
| **Database** | localhost:5432 | PostgreSQL (только в Docker) |

## 📂 Структура проекта

```
neo-fin-ai/
├── neo-fin-ai.sln              ← Откройте этот файл в VS
├── Backend.pyproj              ← Python backend проект
├── run.ps1                      ← PowerShell скрипты
├── run.bat                      ← Batch скрипты
│
├── src/                         ← Backend Python код
│   ├── app.py                   ← FastAPI приложение
│   ├── controllers/             ← Бизнес-логика
│   ├── routers/                 ← API маршруты
│   ├── core/                    ← Ядро (агент, промпты)
│   ├── db/                      ← Конфигурация БД
│   └── models/                  ← Data models
│
├── frontend/                    ← React приложение
│   ├── Frontend.csproj
│   ├── package.json
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── components/
│   │   └── pages/
│   └── index.html
│
├── migrations/                  ← Alembic миграции БД
├── docker-compose.yml           ← Docker конфигурация
├── Dockerfile                   ← Docker образ backend
├── requirements.txt             ← Python зависимости
└── .env                         ← Переменные окружения
```

## 🔧 Локальная разработка (без Docker)

Если хотите работать локально без Docker:

**Требования:**
- Python 3.11+
- Node.js 24+
- PostgreSQL 16+ (локально установленная)

**Шаги:**

1. **Установить Python зависимости:**
```powershell
E:\neo-fin-ai\venv\Scripts\python.exe -m pip install -r requirements.txt
```

2. **Запустить backend в одном терминале:**
```powershell
E:\neo-fin-ai\venv\Scripts\python.exe -m uvicorn src.app:app --reload
```

3. **Запустить frontend в другом терминале:**
```powershell
cd frontend
npm install
npm run dev
```

4. **Frontend будет доступен на:** http://localhost:5173

## 🐛 Решение проблем

### Docker не запускается
```powershell
# Проверить, запущен ли Docker daemon
docker ps

# Если нет, запустить Docker Desktop
```

### Ошибка соединения с БД
```powershell
# Перезапустить контейнеры с очисткой
.\run.ps1 -Command clean
.\run.ps1 -Command docker-up
```

### Логи показывают ошибки миграций
```powershell
# Посмотреть полные логи
docker-compose logs backend

# Проверить состояние БД
docker-compose logs db
```

### Python не найден в venv
```powershell
# Пересоздать виртуальное окружение
python -m venv venv
E:\neo-fin-ai\venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 📝 Исправленные проблемы

✅ **Смешанная индентация** в settings.py — исправлено  
✅ **AI отключен** в analyze.py — раскомментирован реальный вызов агента  
✅ **Миграции БД** — добавлена проверка в entrypoint.sh  
✅ **CSS Dropzone** — добавлены импорты стилей  
✅ **Мёртвый код** — удалён src/core/database.py  

## 💡 Полезные команды

```powershell
# Просмотр логов в реальном времени
docker-compose logs -f backend

# Перезагрузить backend сервис
docker-compose restart backend

# Остановить только backend
docker-compose stop backend

# Удалить всё включая БД данные
docker-compose down -v

# Проверить список контейнеров
docker ps -a
```

## 🎓 Дополнительно

- **API Testing**: используйте Swagger UI на http://localhost:8000/docs
- **Database Management**: используйте pgAdmin или любой PostgreSQL клиент
- **Logs Monitoring**: `docker-compose logs -f` для всех сервисов

---

**Готово! 🎉 Теперь откройте `neo-fin-ai.sln` в Visual Studio и начните разработку!**
