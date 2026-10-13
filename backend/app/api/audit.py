from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.models.ops import AuditEvent

router = APIRouter(prefix="/audit", tags=["audit"])
Db = Annotated[Session, Depends(get_session)]


@router.get("")
def list_audit(
    session: Db,
    actor: str | None = None,
    incident: int | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict[str, Any]]:
    q = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if actor:
        q = q.where(AuditEvent.actor == actor)
    if incident is not None:
        q = q.where(AuditEvent.incident_id == incident)
    return [
        {
            "id": e.id,
            "ts": e.ts.isoformat(),
            "actor": e.actor,
            "incident_id": e.incident_id,
            "action": e.action,
            "detail": e.detail,
            "is_demo": e.is_demo,
        }
        for e in session.scalars(q)
    ]
