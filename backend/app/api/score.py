import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.harness.scoring import compute

router = APIRouter(prefix="/score", tags=["score"])
Db = Annotated[Session, Depends(get_session)]
RESULTS = Path(__file__).resolve().parents[3] / "docs" / "results.json"


@router.get("")
def score(session: Db) -> dict[str, Any]:
    out = compute(session)
    # Baseline comparison comes from a recorded harness run (Phase 8), never computed here.
    out["comparison"] = json.loads(RESULTS.read_text()) if RESULTS.exists() else None
    return out
