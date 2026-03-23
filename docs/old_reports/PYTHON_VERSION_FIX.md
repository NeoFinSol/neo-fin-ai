# ⚠️ РЕШЕНИЕ: Python 3.9.13 не совместим

## Проблема
Вы используете **Python 3.9.13**, но проект требует **Python 3.11+**

```
python --version
Python 3.9.13
```

## Почему это проблема?

Некоторые зависимости (особенно `pdfplumber 0.12.0`) требуют Python 3.10+:
- ❌ `pdfminer.six` для Python 3.9 недоступен
- ❌ Некоторые type hints требуют Python 3.10+
- ❌ `numpy 2.x` требует Python 3.10+

---

## ✅ РЕШЕНИЕ 1: Обновить Python на 3.11+ (РЕКОМЕНДУЕТСЯ)

### Для Windows:

#### Способ A: Через python.org (официально)
1. Откройте https://www.python.org/downloads/
2. Скачайте **Python 3.11** или **Python 3.12**
3. Запустите установщик
4. ✅ Отметьте "Add Python to PATH"
5. Нажмите "Install"

#### Способ B: Через Microsoft Store
1. Откройте Microsoft Store
2. Поищите "Python 3.11"
3. Нажмите "Install"
4. Дождитесь установки

#### Способ C: Через chocolatey (если установлен)
```powershell
choco install python --version=3.11.0
```

### Проверка после установки:
```powershell
python --version
# Должно быть: Python 3.11.x или 3.12.x
```

---

## ✅ РЕШЕНИЕ 2: Использовать несколько версий Python

Если вам нужна Python 3.9 для чего-то другого, можно установить обе версии:

### Установить Python 3.11 рядом с 3.9:

1. Скачайте Python 3.11 с https://www.python.org/downloads/
2. При установке выберите **Custom Install**
3. Измените путь на что-то вроде: `C:\Python311`
4. ✅ Отметьте "Add Python to PATH"

### Использовать нужную версию:

```powershell
# Используйте Python 3.11 для этого проекта
C:\Python311\python.exe --version

# Или создайте полный путь для проекта
C:\Python311\python.exe -m venv env
.\env\Scripts\Activate.ps1
```

---

## ⚠️ РЕШЕНИЕ 3: Понизить требования (НЕ РЕКОМЕНДУЕТСЯ)

Если вы **обязательно** должны использовать Python 3.9:

### Отредактируйте requirements.txt:

```
# Замените эти версии на совместимые с Python 3.9:
pdfplumber~=0.11.0   # Вместо 0.12.0
numpy<2.0            # Вместо 2.x
```

**Однако** это может привести к другим ошибкам, потому что:
- ❌ Старые версии имеют баги
- ❌ Теряется поддержка новых функций
- ❌ Могут быть уязвимости безопасности

---

## 🚀 Рекомендуемый путь (3 минуты)

### Шаг 1: Установить Python 3.11
```
Откройте https://www.python.org/downloads/
Скачайте Python 3.11
Установите с галочкой "Add Python to PATH"
```

### Шаг 2: Проверить что он установлен
```powershell
python --version
# Должно быть 3.11.x или выше
```

### Шаг 3: Запустить инициализацию
```powershell
.\init_project.ps1
```

### Шаг 4: Всё работает!
```powershell
python -m pytest tests/test_auth.py -v
```

---

## 🔧 Если Python 3.11 не установился в PATH

Используйте полный путь:

```powershell
# Найдите где установлен Python 3.11
Get-Command python

# Или используйте через программы
C:\Users\[YourUsername]\AppData\Local\Programs\Python\Python311\python.exe --version
```

Если нужен полный путь каждый раз, создайте alias:

```powershell
# Добавьте в профиль PowerShell ($PROFILE):
Set-Alias python311 'C:\Users\[YourUsername]\AppData\Local\Programs\Python\Python311\python.exe'

# Тогда используйте:
python311 --version
python311 -m venv env
```

---

## ❌ Если вы видите эту ошибку при запуске init_project.ps1:

```
ERROR: pdfminer.six==20251230 not available for Python 3.9
```

**Это означает:**
- ❌ Python 3.9 всё ещё активен
- ✅ Нужно установить Python 3.11
- ✅ Нужно пересоздать виртуальное окружение

### Исправление:

```powershell
# 1. Проверьте версию Python (должна быть 3.11+)
python --version

# 2. Удалите старое окружение
Remove-Item -Recurse -Force env

# 3. Создайте новое окружение с Python 3.11
python -m venv env

# 4. Активируйте
.\env\Scripts\Activate.ps1

# 5. Переустановите зависимости
python -m pip install -r requirements.txt
```

---

## ✅ Проверочный список

После обновления Python:

- [ ] `python --version` показывает 3.11 или выше
- [ ] `.\init_project.ps1` выполнен без ошибок
- [ ] `python -m pytest tests/test_auth.py -v` проходит
- [ ] `python src/app.py` запускает сервер

---

## 📝 Быстрая справка версий Python

| Версия | Статус | Поддержка |
|--------|--------|----------|
| 3.8 | ❌ Старый | Заканчивается |
| 3.9 | ⚠️ Старый | Скоро заканчивается |
| 3.10 | ✅ Хороший | Нормально |
| 3.11 | ✅✅ Отличный | **Рекомендуется** |
| 3.12 | ✅✅ Новый | Поддержка растёт |

**Используйте: Python 3.11 или 3.12**

---

## 💡 Если вы разработчик и вам часто нужны разные версии Python

Используйте **pyenv** или **conda**:

```powershell
# Через conda (рекомендуется)
conda install -c conda-forge python=3.11
conda activate myenv

# Или через pyenv-win
# https://github.com/pyenv-win/pyenv-win
```

---

## 🎯 ГЛАВНОЕ

**Python 3.9 → Python 3.11** (5 минут установки)

После этого всё будет работать! 🚀

---

**Версия:** 1.0
**Дата:** 2025-01-15
