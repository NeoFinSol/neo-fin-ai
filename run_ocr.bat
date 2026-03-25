@echo off
REM Запуск проверки с правильным PATH
set "PATH=C:\Program Files\gs\gs10.03.0\bin;%PATH%"
set "PATH=C:\Program Files\Tesseract-OCR;%PATH%"
set "PATH=C:\Program Files\poppler\Library\bin;%PATH%"
python %~dp0check_ocr.py
pause
