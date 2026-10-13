from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.detector.engine import baseline_ms
from app.journeys.definitions import JOURNEYS
from app.journeys.runner import runner
from app.models.journeys import JourneyRun

router = APIRouter(prefix="/journeys", tags=["journeys"])
Db = Annotated[Session, Depends(get_session)]


def journey_view(session: Session, journey_id: str) -> dict[str, Any]:
    runs = list(
        session.scalars(
            select(JourneyRun).where(JourneyRun.journey == journey_id).order_by(JourneyRun.id.desc()).limit(30)
        )
    )
    latest = runs[0] if runs else None
    base = baseline_ms(session, journey_id, datetime(9999, 1, 1))
    return {
        "id": journey_id,
        "label": JOURNEYS[journey_id]["label"],
        "status": "unknown" if latest is None else ("ok" if latest.ok else "failed"),
        "latest": None
        if latest is None
        else {
            "started_at": latest.started_at.isoformat(),
            "ok": latest.ok,
            "total_ms": latest.total_ms,
            "failed_step": latest.failed_step,
            "steps": latest.steps,
        },
        "history_ms": [r.total_ms for r in reversed(runs)],
        "history_ok": [r.ok for r in reversed(runs)],
        "baseline_mean_ms": round(sum(base) / len(base), 1) if base else None,
    }


@router.get("")
def list_journeys(session: Db) -> list[dict[str, Any]]:
    return [journey_view(session, j) for j in JOURNEYS]


@router.post("/{journey_id}/run")
async def run_now(journey_id: str, request: Request, session: Db) -> dict[str, Any]:
    if journey_id not in JOURNEYS:
        raise HTTPException(404, f"unknown journey: {journey_id}")
    await runner.run_once(journey_id, request.app)
    return journey_view(session, journey_id)
