#!/usr/bin/env python
"""Проверка установки Ghostscript и Tesseract."""
import subprocess
import sys

print("=" * 60)
print("ПРОВЕРКА УСТАНОВКИ ЗАВИСИМОСТЕЙ")
print("=" * 60)

# Проверка Ghostscript
print("\n1. Ghostscript...")
try:
    result = subprocess.run(['gswin64c', '--version'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        print(f"   ✓ Ghostscript установлен: {result.stdout.strip()}")
    else:
        print(f"   ✗ Ghostscript: ошибка {result.returncode}")
except FileNotFoundError:
    print("   ✗ Ghostscript не найден в PATH")
    print("   → Добавь 'C:\\Program Files\\gs\\gs10.03.0\\bin' в PATH")
except Exception as e:
    print(f"   ✗ Ошибка: {e}")

# Проверка Tesseract
print("\n2. Tesseract OCR...")
try:
    result = subprocess.run(['tesseract', '--version'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        print(f"   ✓ Tesseract: {result.stdout.splitlines()[0]}")
        # Проверка русских языков
        result_lang = subprocess.run(['tesseract', '--list-langs'], capture_output=True, text=True, timeout=5)
        langs = result_lang.stdout.lower()
        if 'rus' in langs or 'russian' in langs:
            print(f"   ✓ Русский язык: доступен")
        else:
            print(f"   ⚠ Русский язык: не найден (переустанови с rus data)")
    else:
        print(f"   ✗ Tesseract: ошибка {result.returncode}")
except FileNotFoundError:
    print("   ✗ Tesseract не найден в PATH")
    print("   → Добавь 'C:\\Program Files\\Tesseract-OCR' в PATH")
except Exception as e:
    print(f"   ✗ Ошибка: {e}")

# Проверка Python пакетов
print("\n3. Python пакеты...")
try:
    import camelot
    print(f"   ✓ camelot-py: {camelot.__version__}")
except ImportError:
    print("   ✗ camelot-py: не установлен")
    print("   → pip install camelot-py[all]")

try:
    import pytesseract
    print(f"   ✓ pytesseract: установлен")
except ImportError:
    print("   ✗ pytesseract: не установлен")
    print("   → pip install pytesseract")

try:
    import pdf2image
    print(f"   ✓ pdf2image: установлен")
except ImportError:
    print("   ✗ pdf2image: не установлен")
    print("   → pip install pdf2image")

print("\n" + "=" * 60)
