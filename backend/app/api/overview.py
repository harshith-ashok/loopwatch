from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.journeys import journey_view
from app.core.db import get_session
from app.journeys.definitions import JOURNEYS
from app.models.journeys import TERMINAL_STATES, Incident

router = APIRouter(prefix="/overview", tags=["overview"])
Db = Annotated[Session, Depends(get_session)]


@router.get("")
def overview(session: Db) -> dict[str, Any]:
    journeys = [journey_view(session, j) for j in JOURNEYS]
    open_incidents = session.scalar(
        select(func.count()).select_from(Incident).where(Incident.state.not_in(TERMINAL_STATES))
    )
    return {
        "journeys_total": len(journeys),
        "journeys_healthy": sum(1 for j in journeys if j["status"] == "ok"),
        "open_incidents": open_incidents or 0,
        "journeys": journeys,
    }
