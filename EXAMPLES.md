# 📖 ПРИМЕРЫ: Как использовать созданные скрипты

## Пример 1️⃣: Первый запуск (Windows PowerShell)

```powershell
# 1. Откройте PowerShell в корне проекта
cd E:\neo-fin-ai

# 2. Запустите скрипт инициализации
.\init_project.ps1

# Результат:
# ============================================================
# [*] NeoFin AI - Project Initialization
# ============================================================
# 
# [*] Checking Python...
# [+] Python 3.11.9
# 
# [+] Virtual environment already exists
# 
# ============================================================
# [*] Updating pip
# ============================================================
# ...
# [+] pytest: pytest 8.3.5
# 
# ============================================================
# [+] Initialization completed!
# ============================================================

# 3. Теперь окружение активировано!
```

---

## Пример 2️⃣: Запуск тестов из VS Code

### Способ A: Через Test Explorer
1. `Ctrl + E, T` - открыть Test Explorer
2. Нажмите кнопку "Run All Tests"
3. Смотрите результаты в Output

### Способ B: Из терминала VS Code
```powershell
# Встроенный терминал уже имеет активированное окружение
python -m pytest tests/ -v

# Результат:
# tests/test_auth.py::TestAuthenticationEnforcement::test_auth_requires_api_key_in_production PASSED
# tests/test_auth.py::TestAuthenticationEnforcement::test_auth_rejects_missing_api_key_in_production PASSED
# ...
# ====================== 279 passed in 117.05s ======================
```

### Способ C: Отладка одного теста
1. Откройте файл `tests/test_auth.py`
2. Нажмите `F5` или выберите `Python: Debug Tests`
3. Выберите конфигурацию из `launch.json`
4. Сможете ставить breakpoints и отлаживать

---

## Пример 3️⃣: Запуск приложения

```powershell
# 1. Убедитесь что окружение активировано
# (если нет, выполните: .\env\Scripts\Activate.ps1)

# 2. Запустите приложение
python src/app.py

# Результат:
# INFO:     Uvicorn running on http://127.0.0.1:8000
# INFO:     Application startup complete

# 3. Откройте браузер
# http://localhost:8000/docs - Swagger UI
# http://localhost:8000/redoc - ReDoc

# 4. Вы можете тестировать API прямо в браузере!
```

---

## Пример 4️⃣: Установка новой зависимости

```powershell
# 1. Добавьте пакет в requirements.txt
# Отредактируйте файл и добавьте, например:
# requests~=2.31.0

# 2. Переустановите зависимости
python -m pip install -r requirements.txt

# Или добавьте напрямую:
python -m pip install requests

# 3. Используйте в коде
import requests
response = requests.get("https://api.example.com")
```

---

## Пример 5️⃣: Проверка кода

```powershell
# Форматирование кода (Black)
black src/ tests/

# Проверка стиля (Flake8)
flake8 src/ tests/

# Проверка типов (MyPy)
mypy src/

# Все проверки вместе
black --check src/ tests/
flake8 src/ tests/
mypy src/
```

---

## Пример 6️⃣: Сборка и развертывание

```powershell
# Локально (для разработки)
python src/app.py

# Docker (для production)
docker-compose build
docker-compose up

# С перестройкой без кэша
docker-compose build --no-cache
docker-compose up -d

# Остановка
docker-compose down
```

---

## Пример 7️⃣: Отладка проблем

### Проблема: ModuleNotFoundError

```powershell
# Причина: окружение не активировано

# Решение:
.\env\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# Проверка:
python -c "import fastapi; print('OK')"
```

### Проблема: pytest не найден

```powershell
# Причина: тестовые зависимости не установлены

# Решение:
python -m pip install -r requirements-dev.txt

# Проверка:
python -m pytest --version
```

### Проблема: Slow pip install

```powershell
# Решение 1: Очистите кэш
python -m pip cache purge

# Решение 2: Используйте --no-cache-dir
python -m pip install -r requirements.txt --no-cache-dir

# Решение 3: Force reinstall
python -m pip install -r requirements.txt --force-reinstall
```

---

## Пример 8️⃣: Работа с виртуальным окружением

```powershell
# Активация окружения
.\env\Scripts\Activate.ps1

# Проверка активации (в начале строки появится (env))
# (env) E:\neo-fin-ai>

# Просмотр установленных пакетов
python -m pip list

# Деактивация окружения
deactivate

# Проверка что деактивировано (нет (env))
# E:\neo-fin-ai>
```

---

## Пример 9️⃣: Запуск конкретного теста

```powershell
# Запустить один тестовый файл
python -m pytest tests/test_auth.py -v

# Запустить один класс тестов
python -m pytest tests/test_auth.py::TestAuthenticationEnforcement -v

# Запустить один метод теста
python -m pytest tests/test_auth.py::TestAuthenticationEnforcement::test_auth_requires_api_key_in_production -v

# Запустить только тесты с маркером "unit"
python -m pytest tests/ -m unit -v

# Запустить с покрытием кода (coverage)
python -m pytest tests/ --cov=src --cov-report=html
# Результат в: htmlcov/index.html
```

---

## Пример 🔟: Интеграция с Git

```powershell
# Используйте pre-commit hooks для автоматической проверки
pre-commit install

# Теперь при каждом commit будет:
# - Форматирование (Black)
# - Проверка синтаксиса (Flake8)
# - Проверка типов (MyPy)
# - Проверка безопасности (Bandit)

# Ручное выполнение всех проверок
pre-commit run --all-files
```

---

## 🎯 Рекомендуемый рабочий процесс

### Ежедневный процесс:
```powershell
# 1. Откройте терминал
cd E:\neo-fin-ai

# 2. Активируйте окружение
.\env\Scripts\Activate.ps1

# 3. Обновите зависимости
python -m pip install -r requirements.txt

# 4. Запустите тесты
python -m pytest tests/ -v

# 5. Запустите приложение
python src/app.py

# 6. Начните разработку!
```

### Перед сохранением кода:
```powershell
# 1. Проверьте тесты
python -m pytest tests/ -v

# 2. Проверьте кодстайл
black src/
flake8 src/

# 3. Сохраните в Git
git add .
git commit -m "Fix: описание изменения"
git push
```

---

## ✅ Проверочный список

- [ ] `.\init_project.ps1` выполнен
- [ ] `python -m pytest --version` работает
- [ ] `python -m pytest tests/test_auth.py -v` проходит
- [ ] `python src/app.py` запускается
- [ ] http://localhost:8000/docs открывается
- [ ] Тесты запускаются из VS Code
- [ ] Можете отлаживать тесты (F5)

**Если всё ✅ - готово к разработке!**

---

**Версия:** 1.0  
**Дата:** 2025-01-15
