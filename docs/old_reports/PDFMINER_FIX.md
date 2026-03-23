# ⚠️ ИСПРАВЛЕНИЕ: Проблема с pdfminer.six

## Проблема
```
ERROR: Could not find a version that satisfies the requirement pdfminer.six==20251230
```

## Причина
- `pdfplumber~=0.11.9` требует `pdfminer.six==20251230`
- Эта версия требует Python 3.10+
- В вашем окружении используется Python 3.9 или другой интерпретатор

## Решение

### Вариант 1: Обновить pdfplumber (РЕКОМЕНДУЕТСЯ)

`requirements.txt` уже обновлен с `pdfplumber~=0.12.0`

Переустановите:
```powershell
python -m pip install -r requirements.txt --no-cache-dir --force-reinstall
```

### Вариант 2: Проверить версию Python

Убедитесь что используется Python 3.11:
```powershell
python --version
```

Если версия меньше 3.11, установите Python 3.11+ с https://python.org

### Вариант 3: Использовать правильный интерпретатор

Используйте полный путь к Python 3.11:
```powershell
C:\Users\User\AppData\Local\Programs\Python\Python311\python.exe -m pip install -r requirements.txt
```

## Проверка

После исправления проверьте:
```powershell
python -m pytest tests/test_auth.py -v
```

Должно работать без ошибок!
