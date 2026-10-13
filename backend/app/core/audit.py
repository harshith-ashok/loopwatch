from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.events import bus
from app.models.ops import AuditEvent

# `harness` is an addition to the six actors in CLAUDE.md: fault injection is not
# something the detector, agents, policy, executor or verifier did.
Actor = Literal["detector", "agent", "policy", "human", "executor", "verifier", "harness"]


def record(
    session: Session,
    actor: Actor,
    action: str,
    detail: dict[str, Any] | None = None,
    incident_id: int | None = None,
) -> AuditEvent:
    event = AuditEvent(actor=actor, action=action, detail=detail or {}, incident_id=incident_id)
    session.add(event)
    session.commit()
    bus.publish("audit.appended", {"id": event.id, "actor": actor, "action": action})
    return event
