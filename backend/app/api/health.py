from fastapi import APIRouter

from app.core.db import db_ok

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    database = db_ok()
    return {"status": "ok" if database else "degraded", "db": database}
