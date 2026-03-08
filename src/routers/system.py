from fastapi import APIRouter


router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
