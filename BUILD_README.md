# 🚀 NeoFin AI - Справка по сборке проекта

## ❓ Почему я не могу начать сборку?

> Это Python проект. "Сборка" в Python означает **установка зависимостей**, а не компиляция кода.

---

## ✅ Решение в 3 шага

### 1. Инициализировать проект
```powershell
.\init_project.ps1
```

Или вручную:
```powershell
python -m venv env
.\env\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. Проверить установку
```powershell
python -m pytest --version
python -m pytest tests/test_auth.py -v
```

### 3. Запустить приложение
```powershell
python src/app.py
```

---

## 📚 Документация

| Файл | Описание |
|------|---------|
| **QUICK_START.md** | ⭐ Быстрый старт (начните отсюда!) |
| **BUILDING.md** | Почему не собирается & как исправить |
| **BUILD_GUIDE.md** | Полное руководство по сборке |
| **GETTING_STARTED.md** | Введение в проект |
| **DATABASE_SETUP_GUIDE.md** | Настройка БД |

---

## 🛠️ Создано для вас

✅ Скрипты инициализации:
- `init_project.ps1` - PowerShell (рекомендуется)
- `init_project.py` - Python (кроссплатформа)
- `init_project.bat` - Batch (Windows)

✅ VS Code конфигурация:
- `.vscode/settings.json` - настройки
- `.vscode/launch.json` - отладка
- `.vscode/extensions.json` - расширения

✅ Конфиги:
- `setup.py` - для установки как пакета

✅ Документация:
- `BUILD_GUIDE.md` - подробное руководство
- `BUILDING.md` - объяснение проблемы
- `QUICK_START.md` - краткий гайд

---

## 🎯 Что было исправлено

✅ Обновлены зависимости в `requirements.txt`
✅ Удалены несовместимые пакеты из `requirements-dev.txt`
✅ Обновлен pip с 22.x на 26.x
✅ Добавлены конфигурации VS Code
✅ Созданы скрипты инициализации

---

## 📊 Статус

- ✅ Python 3.11.9
- ✅ 279 тестов проходят
- ✅ FastAPI, SQLAlchemy, Pydantic готовы
- ✅ pytest работает

---

**Начните с: QUICK_START.md → BUILDING.md → BUILD_GUIDE.md**
