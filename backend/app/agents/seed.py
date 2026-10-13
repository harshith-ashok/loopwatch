"""Synthetic past incidents so memory.similar has history. These are written by hand to
look like closed incidents; they are not records of real events."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.embedding import embed
from app.models.incidents import PastIncident

SEED = [
    ("Order confirmation: 'Order confirmed' failed: order still 'paid' after 3000 ms; queue depth rising, no consumers", "worker_stalled", "restart_service", "resolved"),
    ("Order confirmation failed: orders paid but never confirmed, order worker consumer count 0", "worker_stalled", "restart_service", "resolved"),
    ("Payment: 'Charge card' failed: gateway timeout (504); primary gateway slow, fallback healthy", "gateway_degraded", "switch_endpoint", "resolved"),
    ("Payment latency p95 over baseline with 22% timeouts on primary payment gateway", "gateway_degraded", "switch_endpoint", "resolved"),
    ("Edge node: temperature 85 C above 70 C for 10 s; fan 0 rpm on fulfillment hub", "cooling_fault", "power_cycle_device", "escalated"),
    ("Edge node temperature limit exceeded, fan stalled, hub acknowledgements slow", "cooling_fault", "power_cycle_device", "escalated"),
    ("Edge node: no heartbeat for 6 s (3 missed); hub acknowledges step failing with 503", "link_lost", "switch_endpoint", "mitigated"),
    ("Hub unreachable, signal strength fell to -92 dBm before the node went silent", "link_lost", "switch_endpoint", "mitigated"),
]


def seed_past_incidents(session: Session) -> int:
    if session.scalar(select(PastIncident.id).limit(1)) is not None:
        return 0
    for summary, cause, action, outcome in SEED:
        session.add(PastIncident(summary=summary, cause_key=cause, action=action, outcome=outcome, embedding=embed(summary)))
    session.commit()
    return len(SEED)
