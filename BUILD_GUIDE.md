# Инструкция по сборке проекта NeoFin AI

## 📋 Обзор

NeoFin AI - это **Python проект**, который не требует традиционной компиляции как .NET проекты. 
"Сборка" проекта в контексте Python означает:
1. ✅ Установку зависимостей
2. ✅ Проверку синтаксиса
3. ✅ Запуск тестов

---

## 🚀 Быстрый старт

### Вариант 1: Автоматический запуск при сборке (рекомендуется)

Когда вы нажимаете `Build` в Visual Studio, выполняется следующее:

```powershell
# 1. Установка/обновление зависимостей
python -m pip install -r requirements.txt

# 2. Установка dev зависимостей (опционально)
python -m pip install -r requirements-dev.txt

# 3. Проверка что pytest установлен
python -m pytest --version
```

### Вариант 2: Ручной запуск из PowerShell

```powershell
# 1. Перейдите в директорию проекта
cd E:\neo-fin-ai

# 2. Создайте виртуальное окружение (если еще не создано)
python -m venv env

# 3. Активируйте окружение
.\env\Scripts\Activate.ps1

# 4. Установите зависимости
python -m pip install -r requirements.txt

# 5. Установите dev зависимости
python -m pip install -r requirements-dev.txt
```

### Вариант 3: Использование PowerShell скрипта

```powershell
# Используйте предоставленный скрипт
.\run.ps1
```

---

## 🔧 Запуск тестов после сборки

После того как сборка завершена, вы можете запустить тесты:

### Из Visual Studio:
- **Test Explorer** (Ctrl + E, T) → Нажмите кнопку "Run All"
- Или щелкните правой кнопкой на тесте и выберите "Run"

### Из PowerShell:
```powershell
# Запустить все тесты
python -m pytest tests/ -v

# Запустить конкретный тестовый файл
python -m pytest tests/test_auth.py -v

# Запустить с покрытием кода
python -m pytest tests/ --cov=src --cov-report=html
```

---

## 🛠️ Решение проблем при сборке

### Проблема: "Python не найден"
**Решение:**
```powershell
# Убедитесь, что Python установлен и в PATH
python --version

# Если не работает, используйте полный путь
C:\Users\User\AppData\Local\Programs\Python\Python311\python.exe --version
```

### Проблема: "pip install завис на зависимостях"
**Решение:**
```powershell
# Очистите кэш pip
python -m pip cache purge

# Переустановите зависимости
python -m pip install -r requirements.txt --no-cache-dir --force-reinstall
```

### Проблема: "Ошибка совместимости пакетов"
**Решение:**
```powershell
# Обновите все пакеты
python -m pip install --upgrade pip setuptools wheel

# Переустановите requirements
python -m pip install -r requirements.txt
```

### Проблема: "ModuleNotFoundError при запуске тестов"
**Решение:**
```powershell
# Убедитесь, что используется правильный интерпретатор
where python

# Убедитесь, что все зависимости установлены
python -m pip list | grep pytest
python -m pip list | grep pydantic
```

---

## 📁 Структура проекта

```
neo-fin-ai/
├── src/                      # Исходный код приложения
│   ├── app.py               # Главное FastAPI приложение
│   ├── core/                # Основная логика (AI, Auth, etc)
│   ├── routers/             # API маршруты
│   ├── models/              # Pydantic модели
│   ├── db/                  # Работа с БД
│   └── analysis/            # Анализ финансовых данных
├── tests/                   # Тестовые файлы
├── frontend/                # React/TypeScript приложение
├── requirements.txt         # Production зависимости
├── requirements-dev.txt     # Development зависимости
├── Backend.pyproj           # Конфиг Python проекта VS
├── Tests.pyproj             # Конфиг тестов VS
└── neo-fin-ai.sln          # Visual Studio Solution файл
```

---

## ⚙️ Переменные окружения

Перед сборкой убедитесь, что настроены переменные окружения:

1. Скопируйте `.env.example` в `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```

2. Отредактируйте `.env` с вашими значениями:
   ```
   DATABASE_URL=postgresql://user:password@localhost/neo_fin_ai
   API_KEY=your-api-key
   GIGACHAT_API_KEY=your-gigachat-key
   ```

---

## 🎯 Непрерывная интеграция

Для автоматизации сборки используйте:

```powershell
# Docker (рекомендуется для production)
docker-compose build

# Или Docker Compose с переопределением
docker-compose -f docker-compose.yml -f docker-compose.override.yml build
```

---

## 📞 Получить справку

- 📖 [GETTING_STARTED.md](./GETTING_STARTED.md) - Полное руководство по началу работы
- 🗄️ [DATABASE_SETUP_GUIDE.md](./DATABASE_SETUP_GUIDE.md) - Настройка БД
- 💬 [GIGACHAT_SETUP.md](./GIGACHAT_SETUP.md) - Интеграция с GigaChat AI
- 🐍 [Python Documentation](https://docs.python.org/)

---

## ✅ Чек-лист для успешной сборки

- [ ] Python 3.11+ установлен
- [ ] pip обновлен до последней версии
- [ ] Виртуальное окружение создано
- [ ] requirements.txt установлены
- [ ] requirements-dev.txt установлены (для разработки)
- [ ] .env файл настроен
- [ ] Тесты запускаются без ошибок
- [ ] Приложение запускается локально

---

**Версия:** 1.0  
**Последнее обновление:** 2025-01-15  
**Разработчик:** NeoFin AI Team
