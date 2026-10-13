"""Decide -> act -> verify for one incident. Every state change writes an audit event."""
import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.causes import CAUSE_LABEL
from app.core import audit
from app.core.events import bus
from app.core.incident_machine import transition
from app.detector.engine import suppress_reopen
from app.executor.actions import execute, rollback
from app.models.incidents import Action, Hypothesis, Ticket
from app.models.journeys import TERMINAL_STATES, Incident
from app.policy.catalog import load_catalog
from app.policy.engine import decide, load_settings
from app.verifier.verify import verify

log = logging.getLogger("flow")

EXECUTED = ("done", "failed", "rolled_back")


def _top_cause(session: Session, incident_id: int) -> str | None:
    return session.scalar(
        select(Hypothesis.cause_key).where(Hypothesis.incident_id == incident_id).order_by(Hypothesis.rank).limit(1)
    )


def escalate(session: Session, inc: Incident, reason: str, actor: str = "policy") -> None:
    """Open an escalation ticket and mark the incident escalated."""
    if inc.state in TERMINAL_STATES:
        return
    session.add(Ticket(incident_id=inc.id, kind="escalation", note=reason))
    session.commit()
    suppress_reopen(inc.dedupe_key, inc.rule)
    audit.record(session, "policy" if actor == "policy" else actor, "escalated", {"reason": reason}, inc.id)  # type: ignore[arg-type]
    transition(session, inc, "escalated", actor, reason)  # type: ignore[arg-type]


def roll_back_all(session: Session, inc: Incident) -> int:
    """Undo executed actions in reverse order."""
    done = list(
        session.scalars(
            select(Action).where(Action.incident_id == inc.id, Action.state == "done").order_by(Action.id.desc())
        )
    )
    for a in done:
        out = rollback(session, a)
        a.state = "rolled_back"
        session.commit()
        audit.record(session, "executor", "action_rolled_back",
                     {"action": a.type, "target": a.target, "result": out, "plan": a.rollback}, inc.id)
    return len(done)


async def proceed(incident_id: int) -> None:
    """Walk the proposed actions through policy and the executor, then verify."""
    from app.core.db import get_sessionmaker

    with get_sessionmaker()() as session:
        inc = session.get(Incident, incident_id)
        if inc is None or inc.state not in ("deciding", "awaiting_approval", "acting"):
            return
        settings = load_settings(session)
        actions = list(session.scalars(select(Action).where(Action.incident_id == incident_id).order_by(Action.id)))

        for a in actions:
            if a.state not in ("proposed", "approved"):
                continue
            if a.type not in load_catalog():  # defence in depth: should be impossible
                a.state = "blocked"
                session.commit()
                escalate(session, inc, f"action {a.type} is not in the catalog")
                return

            if a.state == "proposed":
                d = decide(settings, a.type)
                audit.record(session, "policy", "policy_decision",
                             {"action": a.type, "target": a.target, "mode": d.mode, "reason": d.reason}, incident_id)
                if d.mode == "blocked":
                    a.state = "blocked"
                    session.commit()
                    escalate(session, inc, f"{a.type} is blocked by policy")
                    return
                if d.mode == "approval":
                    a.state, a.mode = "awaiting_approval", "approval"
                    session.commit()
                    transition(session, inc, "awaiting_approval", "policy", d.reason)
                    bus.publish("approval.requested",
                                {"incident_id": incident_id, "action_id": a.id, "type": a.type, "target": a.target})
                    return

            executed = sum(1 for x in actions if x.state in EXECUTED)
            if executed >= settings.budget:
                a.state = "skipped"
                session.commit()
                escalate(session, inc, f"action budget of {settings.budget} exhausted")
                return

            if inc.state != "acting":
                transition(session, inc, "acting", "policy", f"running {a.type}")
            try:
                result = execute(session, a)
                a.state = "done"
                session.commit()
                audit.record(session, "executor", "action_executed",
                             {"action": a.type, "target": a.target, "result": result, "rollback_plan": a.rollback},
                             incident_id)
            except Exception as e:  # noqa: BLE001
                a.state = "failed"
                session.commit()
                audit.record(session, "executor", "action_failed",
                             {"action": a.type, "target": a.target, "error": str(e)[:200]}, incident_id)
                roll_back_all(session, inc)
                escalate(session, inc, f"{a.type} failed: {type(e).__name__}", actor="executor")
                return
            bus.publish("incident.updated", {"id": incident_id, "state": inc.state, "action": a.type})
            await asyncio.sleep(settings.dwell_s())

        if inc.state in TERMINAL_STATES:
            return
        if inc.state != "acting":
            transition(session, inc, "acting", "policy", "no action needed approval")
        transition(session, inc, "verifying", "executor", "all actions executed")
        await asyncio.sleep(settings.dwell_s())

        cause = _top_cause(session, incident_id)
        outcome = await verify(session, incident_id, inc.journey, cause)
        if inc.state in TERMINAL_STATES:  # cancelled while verifying
            return
        if outcome.passed and outcome.cleared_root:
            transition(session, inc, "resolved", "verifier", "journey passed 3 times in a row")
        elif outcome.passed:
            transition(session, inc, "mitigated", "verifier",
                       f"journey works through a fallback; root cause remains ({CAUSE_LABEL.get(cause or '', cause)})")
        else:
            n = roll_back_all(session, inc)
            escalate(session, inc, f"verification failed on run {outcome.runs}; rolled back {n} action(s)",
                     actor="verifier")


async def approve(incident_id: int, operator: str) -> bool:
    from app.core.db import get_sessionmaker

    with get_sessionmaker()() as session:
        inc = session.get(Incident, incident_id)
        a = session.scalar(
            select(Action).where(Action.incident_id == incident_id, Action.state == "awaiting_approval")
        )
        if inc is None or inc.state != "awaiting_approval" or a is None:
            return False
        a.state, a.approved_by = "approved", operator
        session.commit()
        audit.record(session, "human", "approved", {"action": a.type, "target": a.target, "operator": operator},
                     incident_id)
    return True


async def deny(incident_id: int, operator: str) -> bool:
    from app.core.db import get_sessionmaker

    with get_sessionmaker()() as session:
        inc = session.get(Incident, incident_id)
        a = session.scalar(
            select(Action).where(Action.incident_id == incident_id, Action.state == "awaiting_approval")
        )
        if inc is None or inc.state != "awaiting_approval" or a is None:
            return False
        a.state = "denied"
        session.commit()
        audit.record(session, "human", "denied", {"action": a.type, "target": a.target, "operator": operator},
                     incident_id)
        escalate(session, inc, f"{operator} denied {a.type}", actor="human")
    return True
