# 🚀 QUICK START AFTER CRITICAL FIXES

## 5 минут до готовности к разработке

---

## ✅ ШАГ 1: Создать .env файл (1 минута)

```powershell
# Перейти в папку фронтенда
cd frontend

# Скопировать шаблон
Copy-Item .env.example .env.local

# Вернуться в корень
cd ..
```

---

## ✅ ШАГ 2: Заполнить переменные (1 минута)

**Откройте `frontend/.env.local` и заполните:**

```env
# API Configuration
VITE_API_BASE_URL=http://localhost:8000
VITE_API_KEY=your_production_key_here
VITE_DEV_API_KEY=dev_test_key_12345
VITE_ENV=development

# Feature Flags
VITE_ENABLE_DEBUG=false
VITE_ENABLE_MOCK_DATA=false

# Timeout
VITE_API_TIMEOUT=30000
```

**⚠️ ВАЖНО:** Не коммитьте этот файл! Он в `.gitignore`.

---

## ✅ ШАГ 3: Активировать окружение (30 секунд)

```powershell
# Активировать Python окружение
.\env\Scripts\Activate.ps1

# Проверить что работает
python --version
# Ожидаемый результат: Python 3.12.10
```

---

## ✅ ШАГ 4: Запустить приложение (1 минута)

**Вариант A: Используя скрипт (рекомендуется)**
```powershell
# Запустить скрипт
.\run.ps1

# Выбрать опцию:
# 4 - Backend (Local)
# 5 - Frontend (Local)
# 6 - Install dependencies
```

**Вариант B: Вручную**
```powershell
# Терминал 1 - Backend
python -m uvicorn src.app:app --reload

# Терминал 2 - Frontend
cd frontend
npm run dev
```

---

## ✅ ШАГ 5: Проверить что работает (1 минута)

### Backend
```
http://localhost:8000
http://localhost:8000/docs (Swagger UI)
```

### Frontend
```
http://localhost:5173
```

### Проверка CORS
1. Откройте DevTools (F12)
2. Перейти на Frontend
3. Нет ошибок про CORS?
4. ✅ Готово!

---

## 🎯 После этого можете:

```powershell
# Запустить тесты
python -m pytest tests/test_auth.py -v

# Запустить все тесты
python -m pytest tests/ -v

# Запустить с покрытием
python -m pytest tests/ --cov=src --cov-report=html

# Форматировать код
black src/ tests/

# Проверить стиль
flake8 src/ tests/

# Проверить типы
mypy src/
```

---

## ⚠️ Если что-то не работает

### Ошибка: "Virtual environment not found"
```powershell
# Создать окружение
python -m venv env

# Активировать
.\env\Scripts\Activate.ps1

# Установить зависимости
python -m pip install -r requirements.txt
```

### Ошибка: "CORS error"
```
1. Проверить что frontend/.env.local создан
2. Перезагрузить backend и frontend
3. Очистить кэш браузера (Ctrl+Shift+Delete)
```

### Ошибка: "X-API-Key header not allowed"
```
1. Проверить что src/app.py содержит X-API-Key
2. Перезагрузить backend
3. Проверить консоль браузера
```

### Ошибка: "Модуль не найден"
```powershell
# Переустановить зависимости
python -m pip install -r requirements.txt --force-reinstall

# Или очистить кэш
pip cache purge
python -m pip install -r requirements.txt
```

---

## 🔍 Проверочный список

- [ ] ✅ frontend/.env.local создан
- [ ] ✅ Переменные окружения заполнены
- [ ] ✅ Python окружение активировано
- [ ] ✅ Backend запускается на http://localhost:8000
- [ ] ✅ Frontend запускается на http://localhost:5173
- [ ] ✅ Нет CORS ошибок в консоли
- [ ] ✅ API документация доступна
- [ ] ✅ Тесты проходят

---

## 📊 Что изменилось?

| До | После |
|----|--------|
| ❌ Хардкод ключей в коде | ✅ Ключи в .env.local |
| ❌ CORS без X-API-Key | ✅ CORS включает X-API-Key |
| ❌ Жесткие пути в скриптах | ✅ Относительные пути |

---

## 🚀 Готово к разработке!

Просто откройте VS Code и начните писать код. 🎉

```powershell
.\env\Scripts\Activate.ps1
.\run.ps1
```

---

**Время прочтения:** 5 минут
**Время внедрения:** 5 минут
**Всего:** 10 минут ⚡

Вопросы? → CRITICAL_FIXES_REPORT.md
