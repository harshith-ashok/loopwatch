from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import get_session
from app.demo.seed import remove_demo, seed_demo

router = APIRouter(prefix="/demo", tags=["demo"])
Db = Annotated[Session, Depends(get_session)]


@router.post("/seed")
def seed(session: Db) -> dict[str, Any]:
    out = seed_demo(session)
    audit.record(session, "human", "demo_data_seeded", out)
    return out


@router.delete("")
def clear(session: Db) -> dict[str, Any]:
    out = remove_demo(session)
    audit.record(session, "human", "demo_data_removed", out)
    return out
