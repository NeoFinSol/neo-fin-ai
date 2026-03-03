from typing import Any
from pathlib import Path
import tempfile

import pdfplumber
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from app.core.extractor import extract_metrics
from app.core.ratios import calculate_ratios
from app.core.scoring import calculate_score
from app.models.schemas import AnalyzeResponse, Metric, Ratio


router = APIRouter()


@router.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/analyze", response_model=AnalyzeResponse, tags=["analysis"])
async def analyze_pdf(file: UploadFile = File(...)) -> Any:
    """
    Эндпоинт анализа PDF.

    На текущем этапе пайплайн выглядит так:
    - приём PDF;
    - извлечение текста (pdfplumber для текстовых PDF);
    - rule-based извлечение ключевых показателей;
    - расчёт набора стандартных финансовых коэффициентов;
    - черновой интегральный скоринг по 100-балльной шкале.
    """
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Ожидался PDF-файл")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_path = Path(tmp.name)
            content = await file.read()
            tmp.write(content)

        raw_text = ""
        try:
            with pdfplumber.open(tmp_path) as pdf:
                pages_text = [page.extract_text() or "" for page in pdf.pages]
                raw_text = "\n".join(pages_text)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при извлечении текста из PDF: {e}",
            ) from e

        warnings: list[str] = []
        if not raw_text.strip():
            warnings.append("Не удалось извлечь текст из PDF или файл пустой.")

        core_metrics = extract_metrics(raw_text)
        core_ratios = calculate_ratios(core_metrics)
        score = calculate_score(core_ratios)

        metrics = [
            Metric(
                name=m.name,
                value=m.value,
                unit=m.unit,
                year=m.year,
                confidence_score=m.confidence_score,
                source_fragment=m.source_fragment,
            )
            for m in core_metrics
        ]
        ratios = [
            Ratio(
                name=r.name,
                value=r.value,
                unit=r.unit,
                year=r.year,
                formula=r.formula,
                category=r.category,
            )
            for r in core_ratios
        ]

        response = AnalyzeResponse(
            raw_text=raw_text,
            warnings=warnings,
            metrics=metrics,
            ratios=ratios,
            score=score,
            nlp_summary=None,
            risks=[],
            opportunities=[],
            recommendations=[],
            news=[],
        )
        return JSONResponse(content=response.model_dump())
    finally:
        if "tmp_path" in locals() and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

