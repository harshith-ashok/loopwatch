"""Incident lifecycle: states, legal transitions, stage mapping. All changes go through here
so every transition writes an audit event (hard rule 8) and notifies the console."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.audit import Actor
from app.core.events import bus
from app.models.incidents import Evidence, Verification
from app.models.journeys import TERMINAL_STATES, Incident

REQUIRED_PASSES = 3
STAGES = ["detect", "investigate", "decide", "act", "verify"]

# Which stage is "current" for each state. Terminal states sit at the end of verify.
STAGE_OF_STATE = {
    "investigating": "investigate",
    "deciding": "decide",
    "awaiting_approval": "decide",
    "acting": "act",
    "verifying": "verify",
}

TRANSITIONS: dict[str, set[str]] = {
    "investigating": {"deciding", "false_positive", "escalated"},
    "deciding": {"awaiting_approval", "acting", "escalated"},
    "awaiting_approval": {"acting", "escalated"},
    "acting": {"verifying", "awaiting_approval", "escalated"},
    "verifying": {"resolved", "mitigated", "escalated"},
}
# Cancelling is an operator or harness decision and is legal from any non-terminal state.
for _state in list(TRANSITIONS):
    TRANSITIONS[_state].add("cancelled")


class IllegalTransition(Exception):
    pass


def stage_of(state: str) -> str:
    return STAGE_OF_STATE.get(state, "verify")


def transition(
    session: Session, incident: Incident, new_state: str, actor: Actor, reason: str = ""
) -> Incident:
    old = incident.state
    if new_state not in TRANSITIONS.get(old, set()):
        raise IllegalTransition(f"{old} -> {new_state} is not allowed")
    if new_state in ("resolved", "mitigated"):
        # Hard rule 5: closing needs 3 consecutive passing journey runs on record.
        recent = list(
            session.scalars(
                select(Verification.passed)
                .where(Verification.incident_id == incident.id)
                .order_by(Verification.id.desc())
                .limit(REQUIRED_PASSES)
            )
        )
        if len(recent) < REQUIRED_PASSES or not all(recent):
            raise IllegalTransition(f"{new_state} needs {REQUIRED_PASSES} consecutive passing verifications")
    incident.state = new_state
    if new_state in TERMINAL_STATES:
        incident.closed_at = datetime.now(timezone.utc)
    session.commit()
    audit.record(
        session,
        actor,
        "state_changed",
        {"from": old, "to": new_state, "reason": reason},
        incident_id=incident.id,
    )
    bus.publish("incident.updated", {"id": incident.id, "state": new_state, "stage": stage_of(new_state)})
    return incident


def add_evidence(
    session: Session, incident_id: int, tool: str, args: dict, result: dict
) -> Evidence:
    """Store a tool result as the next evidence ref (E1, E2, ...) for the incident."""
    n = len(session.scalars(select(Evidence.id).where(Evidence.incident_id == incident_id)).all())
    row = Evidence(incident_id=incident_id, ref=f"E{n + 1}", tool=tool, args=args, result=result)
    session.add(row)
    session.commit()
    return row
