"""The executor. It runs only catalog actions, each capturing the state needed to roll back."""
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.edge.store import store
from app.models.incidents import Action, Ticket
from app.policy.catalog import load_catalog
from app.shop.faults import state
from app.shop.logs import shop_log
from app.shop.worker import worker


class ExecutorError(Exception):
    pass


def _retry(session: Session, a: Action) -> dict[str, Any]:
    if a.target == "order-worker":
        return {"requeued": worker.requeue_unconfirmed()}
    return {"retried": a.target}


def _open_ticket(session: Session, a: Action) -> dict[str, Any]:
    t = Ticket(incident_id=a.incident_id, kind="ticket", note=f"Opened by action {a.id} for {a.target}")
    session.add(t)
    session.commit()
    return {"ticket_id": t.id}


def _switch(session: Session, a: Action) -> dict[str, Any]:
    if a.target == "payments-gateway":
        a.before = {"payment_route": state.payment_route}
        state.payment_route = "fallback"
    elif a.target == "hub-ack":
        a.before = {"ack_route": state.ack_route}
        state.ack_route = "manual"
    else:
        raise ExecutorError(f"cannot switch {a.target}")
    shop_log("executor", "endpoint_switched", f"switched {a.target}", level="WARNING", target=a.target)
    return {"switched": a.target}


def _restart(session: Session, a: Action) -> dict[str, Any]:
    if a.target != "order-worker":
        raise ExecutorError(f"cannot restart {a.target}")
    a.before = {"stalled": state.stall}
    worker.restart()
    return {"restarted": a.target}


def _power_cycle(session: Session, a: Action) -> dict[str, Any]:
    node = get_settings().edge_node
    if a.target != node:
        raise ExecutorError(f"unknown device {a.target}")
    a.before = {"ack_route": state.ack_route}
    store.enqueue_command(node, "power_cycle")
    return {"command": "power_cycle", "node": node}


_RUN = {
    "retry_operation": _retry,
    "open_ticket": _open_ticket,
    "switch_endpoint": _switch,
    "restart_service": _restart,
    "power_cycle_device": _power_cycle,
}


def execute(session: Session, a: Action) -> dict[str, Any]:
    if a.type not in _RUN:
        raise ExecutorError(f"not a catalog action: {a.type}")
    if load_catalog()[a.type].risk == "high" and not a.approved_by:
        raise ExecutorError(f"{a.type} is high risk and has no recorded approval")
    result = _RUN[a.type](session, a)
    session.commit()
    return result


def rollback(session: Session, a: Action) -> dict[str, Any]:
    """Undo `execute` using the state it captured. Mirrors the rollback text in the catalog."""
    if a.type == "switch_endpoint":
        if "payment_route" in a.before:
            state.payment_route = a.before["payment_route"]
        if "ack_route" in a.before:
            state.ack_route = a.before["ack_route"]
        out = {"restored": a.before}
    elif a.type == "open_ticket":
        for t in session.query(Ticket).filter(Ticket.incident_id == a.incident_id, Ticket.kind == "ticket"):
            t.state, t.note = "closed", t.note + " | closed by rollback"
        out = {"closed_tickets": True}
    elif a.type == "power_cycle_device":
        # Restore the previous profile (nothing to restore in the simulator) and route
        # acknowledgements to the manual queue so orders keep moving while a person looks.
        state.ack_route = "manual"
        out = {"ack_route": "manual"}
    elif a.type == "restart_service":
        out = {"note": "redeploy previous revision: nothing to redeploy in the demo shop"}
    else:  # retry_operation is idempotent
        out = {"note": "no rollback needed"}
    session.commit()
    return out
