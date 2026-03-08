from pathlib import Path


def is_scanned(pdf_path: Path) -> bool:
    """
    Черновая функция определения, является ли PDF сканом.

    На первых этапах может использовать простую эвристику (например,
    отсутствие извлекаемого текста), позже можно улучшить.
    """
    # TODO: реализовать эвристику определения типа PDF
    return False


def extract_text_from_scanned(pdf_path: Path) -> str:
    """
    Извлечение текста из сканированных PDF с помощью Tesseract.

    Заглушка для будущей реализации.
    """
    # TODO: реализовать OCR через Tesseract
    raise NotImplementedError("OCR для сканов ещё не реализован")


def extract_text_from_text_pdf(pdf_path: Path) -> str:
    """
    Извлечение текста из текстовых PDF (может делегировать в pdfplumber).
    """
    # TODO: реализовать извлечение текста для текстовых PDF
    raise NotImplementedError("Извлечение текста для текстовых PDF ещё не реализовано")

