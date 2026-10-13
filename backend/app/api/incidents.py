from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.dispatch import schedule
from app.core.db import get_session
from app.executor import flow
from app.core.incident_machine import stage_of
from app.models.incidents import Action, Evidence, Hypothesis, Verification
from app.models.journeys import Incident
from app.models.ops import AuditEvent
from app.schemas.incidents import (
    ActionOut,
    PendingAction,
    EvidenceOut,
    HypothesisOut,
    IncidentDetail,
    IncidentSummary,
    TimelineEvent,
    VerificationOut,
)

router = APIRouter(prefix="/incidents", tags=["incidents"])
Db = Annotated[Session, Depends(get_session)]


def summary(i: Incident, session: Session) -> IncidentSummary:
    top = session.scalar(
        select(Hypothesis.cause_key).where(Hypothesis.incident_id == i.id).order_by(Hypothesis.rank).limit(1)
    )
    pend = session.scalar(
        select(Action).where(Action.incident_id == i.id, Action.state == "awaiting_approval").limit(1)
    )
    return IncidentSummary(
        is_demo=i.is_demo,
        top_cause=top,
        pending_action=None
        if pend is None
        else PendingAction(id=pend.id, type=pend.type, target=pend.target, risk=pend.risk, rollback=pend.rollback),
        id=i.id,
        title=i.title,
        journey=i.journey,
        state=i.state,
        stage=stage_of(i.state),
        rule=i.rule,
        signals=i.signals,
        opened_at=i.opened_at.isoformat(),
        closed_at=i.closed_at.isoformat() if i.closed_at else None,
    )


@router.get("", response_model=list[IncidentSummary])
def list_incidents(session: Db) -> list[IncidentSummary]:
    return [summary(i, session) for i in session.scalars(select(Incident).order_by(Incident.id.desc()))]


@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: int, session: Db) -> IncidentDetail:
    inc = session.get(Incident, incident_id)
    if inc is None:
        raise HTTPException(404, "unknown incident")

    def rows(model, order):  # noqa: ANN001
        return session.scalars(select(model).where(model.incident_id == incident_id).order_by(order))

    return IncidentDetail(
        **summary(inc, session).model_dump(),
        timeline=[
            TimelineEvent(id=e.id, ts=e.ts.isoformat(), actor=e.actor, action=e.action, detail=e.detail)
            for e in rows(AuditEvent, AuditEvent.id)
        ],
        evidence=[
            EvidenceOut(
                ref=e.ref, tool=e.tool, args=e.args, result=e.result, created_at=e.created_at.isoformat()
            )
            for e in rows(Evidence, Evidence.id)
        ],
        hypotheses=[
            HypothesisOut(
                rank=h.rank, cause=h.cause, cause_key=h.cause_key, confidence=h.confidence, supporting=h.supporting, weakening=h.weakening
            )
            for h in rows(Hypothesis, Hypothesis.rank)
        ],
        actions=[
            ActionOut(
                id=a.id, type=a.type, target=a.target, risk=a.risk, mode=a.mode, state=a.state,
                rollback=a.rollback, created_at=a.created_at.isoformat(), approved_by=a.approved_by,
            )
            for a in rows(Action, Action.id)
        ],
        verifications=[
            VerificationOut(run_number=v.run_number, passed=v.passed, ms=v.ms, created_at=v.created_at.isoformat())
            for v in rows(Verification, Verification.id)
        ],
    )


class Operator(BaseModel):
    operator: str = "operator"  # authentication is out of scope: a name is recorded, nothing more


@router.post("/{incident_id}/approve")
async def approve(incident_id: int, body: Operator) -> dict[str, bool]:
    name = body.operator.strip()[:64] or "operator"
    if not await flow.approve(incident_id, name):
        raise HTTPException(409, "this incident is not awaiting approval")
    schedule(flow.proceed, incident_id)
    return {"ok": True}


@router.post("/{incident_id}/deny")
async def deny(incident_id: int, body: Operator) -> dict[str, bool]:
    name = body.operator.strip()[:64] or "operator"
    if not await flow.deny(incident_id, name):
        raise HTTPException(409, "this incident is not awaiting approval")
    return {"ok": True}
