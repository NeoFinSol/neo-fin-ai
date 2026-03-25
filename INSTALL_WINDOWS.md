# Установка зависимостей для NeoFin AI (Windows)

**Версии актуальны на**: 2026-03-25

## 1. Ghostscript (для camelot lattice)

**Версия**: 10.03.0  
**Скачать**: https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10030/gs10030w64.exe

**Установка:**
1. Запусти установщик
2. Установи в `C:\Program Files\gs\gs10.03.0`

**Добавить в PATH:**
1. Открой «Изменение системных переменных среды»
2. В разделе «Системные переменные» найди `Path`
3. Добавь: `C:\Program Files\gs\gs10.03.0\bin`
4. Перезапусти терминал

**Проверка:**
```bash
gswin64c --version
# Должно вывести: 10.03.0
```

---

## 2. Tesseract OCR (для распознавания сканов)

**Версия**: 5.5.0.20241111  
**Скачать**: https://github.com/UB-Mannheim/tesseract/wiki/download/tesseract-ocr-w64-setup-5.5.0.exe

**Установка:**
1. Запусти установщик
2. Установи в `C:\Program Files\Tesseract-OCR`
3. **Важно:** при установке выбери **Russian language data**

**Добавить в PATH:**
1. Открой «Изменение системных переменных среды»
2. В разделе «Системные переменные» найди `Path`
3. Добавь: `C:\Program Files\Tesseract-OCR`
4. Перезапусти терминал

**Проверка:**
```bash
tesseract --version
# tesseract 5.5.0
tesseract --list-langs
# Должен быть в списке rus
```

---

## 3. Poppler (для pdf2image + OCR)

**Версия**: 25.12.0  
**Скачать**: https://github.com/oschwartz10612/poppler-windows/releases/download/v25.12.0-Release/Release-25.12.0-0.zip

**Установка:**
1. Распакуй архив в `C:\Program Files\poppler`
2. Переименуй папку из `Release-25.12.0-0` в `poppler` (для простоты)

**Добавить в PATH:**
1. Открой «Изменение системных переменных среды»
2. В разделе «Системные переменные» найди `Path`
3. Добавь: `C:\Program Files\poppler\Library\bin`
4. Перезапусти терминал

**Проверка:**
```bash
pdfinfo -v
# poppler 25.12.0
```

---

## 4. Python зависимости

Установи через pip:

```bash
pip install camelot-py[all]
pip install pytesseract
pip install pdf2image
pip install pdfplumber
pip install PyPDF2
```

---

## 5. Проверка всех зависимостей

Запусти скрипт проверки:

```bash
cd E:\neo-fin-ai
python check_deps.py
```

**Ожидаемый результат:**
```
✓ Ghostscript установлен: 10.03.0
✓ Tesseract: tesseract 5.5.0
✓ Русский язык: доступен
✓ camelot-py: 0.11.0
✓ pytesseract: установлен
✓ pdf2image: установлен
```

---

## 6. Примечания

### Если camelot не работает:
Проверь, что Ghostscript добавлен в PATH:
```bash
gswin64c --version
```

### Если OCR не распознаёт русский:
Переустанови Tesseract с Russian language data или скачай отдельно:
https://github.com/tesseract-ocr/tessdata/raw/main/rus.traineddata

Положи в: `C:\Program Files\Tesseract-OCR\tessdata`

### Для production:
Добавь все пути в системный PATH, чтобы не требовался `.bat` файл.

### OCR производительность:
- 80 страниц = 2-5 минут (pdf2image + tesseract)
- Для ускорения: снизить DPI до 200, использовать multiprocessing
