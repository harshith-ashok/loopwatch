"""Demo data. Hand-written sample history so the console is not empty on first launch.
Everything seeded here is flagged is_demo and excluded from the scorecard, from detector
baselines and from agent evidence. None of it records a real event."""
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.agents.causes import CAUSE_LABEL
from app.journeys.definitions import JOURNEYS, STEP_LABELS
from app.models.incidents import Action, Evidence, Hypothesis, Ticket, Verification
from app.models.journeys import Incident, JourneyRun
from app.models.ops import AuditEvent
from app.policy.catalog import load_catalog

NODE = "fulfillment-hub-01"

# (title, journey, rule, key, final state, cause, actions, approved_by, evidence, minutes_ago, verifs)
SCENARIOS: list[dict[str, Any]] = [
    {
        "title": "Order confirmation: 'Order confirmed' failed: order still 'paid' after 3000 ms",
        "journey": "order", "rule": "step_failure", "key": "confirm", "state": "resolved", "cause": "worker_stalled",
        "actions": [("restart_service", "order-worker")], "approved_by": None, "hours_ago": 70, "verify": [True, True, True],
        "evidence": [
            ("detector.signal", {"rule": "step_failure"}, {"summary": "'Order confirmed' failed: order still 'paid' after 3000 ms"}),
            ("metrics.queue_depth", {}, {"queue_depth": 9, "consumers": 0, "paid_unconfirmed_orders": 9, "oldest_paid_unconfirmed_age_s": 22.4}),
            ("db.payments", {}, {"window": 14, "gateways": {"primary": {"count": 14, "captured": 14, "failed": 0, "mean_latency_ms": 41.0}, "fallback": {"count": 0}}}),
            ("device.health", {}, {"online": True, "temp_c": 41.4, "fan_rpm": 4210}),
            ("memory.similar", {"query": "order confirmed"}, {"matches": [{"similarity": 0.71, "cause_key": "worker_stalled", "action": "restart_service"}]}),
        ],
        "support": ["E2", "E5"], "weak": [("gateway_degraded", ["E3"]), ("cooling_fault", ["E4"])],
    },
    {
        "title": "Payment: 'Charge card' failed: gateway timeout (504)",
        "journey": "payment", "rule": "step_failure", "key": "pay", "state": "resolved", "cause": "gateway_degraded",
        "actions": [("switch_endpoint", "payments-gateway")], "approved_by": None, "hours_ago": 52, "verify": [True, True, True],
        "evidence": [
            ("detector.signal", {"rule": "step_failure"}, {"summary": "'Charge card' failed: gateway timeout (504)"}),
            ("db.payments", {}, {"window": 12, "gateways": {"primary": {"count": 12, "captured": 9, "failed": 3, "mean_latency_ms": 1380.0}, "fallback": {"count": 0}}}),
            ("metrics.queue_depth", {}, {"queue_depth": 0, "consumers": 1, "paid_unconfirmed_orders": 0}),
            ("device.health", {}, {"online": True, "temp_c": 41.0, "fan_rpm": 4190}),
        ],
        "support": ["E2"], "weak": [("worker_stalled", ["E3"])],
    },
    {
        "title": "Edge node: temperature 86.4 C above 70 C for 10 s",
        "journey": "edge", "rule": "temperature_limit", "key": "device", "state": "escalated", "cause": "cooling_fault",
        "actions": [("power_cycle_device", NODE)], "approved_by": "alice", "hours_ago": 30, "verify": [False],
        "evidence": [
            ("detector.signal", {"rule": "temperature_limit"}, {"summary": "temperature 86.4 C above 70 C for 10 s"}),
            ("device.health", {}, {"online": True, "temp_c": 86.4, "fan_rpm": 0, "temp_limit_c": 70}),
            ("device.telemetry", {"n": 10}, {"samples": [{"age_s": 2, "temp_c": 86.4, "fan_rpm": 0}]}),
            ("metrics.queue_depth", {}, {"queue_depth": 0, "consumers": 1}),
        ],
        "support": ["E2", "E3"], "weak": [("worker_stalled", ["E4"])],
    },
    {
        "title": "Edge node: no heartbeat for 6 s (3 missed)",
        "journey": "edge", "rule": "heartbeat_missed", "key": "device", "state": "mitigated", "cause": "link_lost",
        "actions": [("switch_endpoint", "hub-ack"), ("open_ticket", "ops-queue")], "approved_by": None, "hours_ago": 8,
        "verify": [True, True, True],
        "evidence": [
            ("detector.signal", {"rule": "heartbeat_missed"}, {"summary": "no heartbeat for 6 s (3 missed)"}),
            ("device.health", {}, {"seen": True, "online": False, "heartbeat_age_s": 7.1}),
            ("network.ping", {}, {"reachable": False, "basis": "heartbeat age; no ICMP is sent"}),
            ("db.payments", {}, {"window": 10, "gateways": {"primary": {"count": 10, "failed": 0, "mean_latency_ms": 40.0}}}),
        ],
        "support": ["E2", "E3"], "weak": [("gateway_degraded", ["E4"])],
    },
    {
        "title": "Checkout: 'Place order' failed: HTTP 409",
        "journey": "checkout", "rule": "step_failure", "key": "checkout", "state": "false_positive", "cause": None,
        "actions": [], "approved_by": None, "hours_ago": 4, "verify": [], "evidence": [
            ("detector.signal", {"rule": "step_failure"}, {"summary": "'Place order' failed: HTTP 409"}),
        ],
        "support": [], "weak": [],
    },
]


def _ts(base: datetime, seconds: float) -> datetime:
    return base + timedelta(seconds=seconds)


def seed_demo(session: Session) -> dict[str, int]:
    if session.scalar(select(Incident.id).where(Incident.is_demo.is_(True)).limit(1)) is not None:
        return {"skipped": 1}
    rng = random.Random(26)
    now = datetime.now(timezone.utc)
    catalog = load_catalog()
    counts = {"incidents": 0, "journey_runs": 0, "audit_events": 0}

    # Journey history: 40 recent runs per journey so sparklines and baselines have shape.
    base_ms = {"login": 18, "checkout": 55, "payment": 130, "order": 190}
    for jid in JOURNEYS:
        for n in range(40):
            started = now - timedelta(minutes=30) + timedelta(seconds=45 * n)
            total = max(5, int(rng.gauss(base_ms[jid], base_ms[jid] * 0.12)))
            steps = []
            per = total / len(JOURNEYS[jid]["steps"])  # type: ignore[arg-type]
            for sid in JOURNEYS[jid]["steps"]:  # type: ignore[union-attr]
                steps.append({"id": sid, "label": STEP_LABELS[sid], "status": "ok", "ms": max(1, int(per)),
                              "error_kind": None, "detail": None})
            session.add(JourneyRun(journey=jid, started_at=started, ok=True, total_ms=total, failed_step=None,
                                   steps=steps, is_demo=True))
            counts["journey_runs"] += 1

    def audit(actor: str, action: str, ts: datetime, incident_id: int | None, detail: dict[str, Any]) -> None:
        session.add(AuditEvent(ts=ts, actor=actor, action=action, incident_id=incident_id, detail=detail, is_demo=True))
        counts["audit_events"] += 1

    for sc in SCENARIOS:
        opened = now - timedelta(hours=sc["hours_ago"])
        terminal_s = {"resolved": 38, "mitigated": 41, "escalated": 52, "false_positive": 9}[sc["state"]]
        inc = Incident(
            title=sc["title"], journey=sc["journey"], rule=sc["rule"], dedupe_key=sc["key"], state=sc["state"],
            signals={"count": 4, "rules_seen": [sc["rule"]], "first_summary": sc["title"], "demo": True},
            opened_at=opened, closed_at=_ts(opened, terminal_s), is_demo=True,
        )
        session.add(inc)
        session.flush()
        counts["incidents"] += 1
        audit("detector", "incident_opened", opened, inc.id, {"rule": sc["rule"], "key": sc["key"]})

        for n, (tool, args, result) in enumerate(sc["evidence"], start=1):
            session.add(Evidence(incident_id=inc.id, ref=f"E{n}", tool=tool, args=args, result=result,
                                 created_at=_ts(opened, 1 + n)))

        if sc["cause"]:
            audit("agent", "investigation_started", _ts(opened, 1), inc.id, {})
            session.add(Hypothesis(incident_id=inc.id, rank=1, cause=CAUSE_LABEL[sc["cause"]], cause_key=sc["cause"],
                                   confidence=0.91, supporting=sc["support"], weakening=[], created_at=_ts(opened, 8)))
            for rank, (cause, weak) in enumerate(sc["weak"], start=2):
                session.add(Hypothesis(incident_id=inc.id, rank=rank, cause=CAUSE_LABEL[cause], cause_key=cause,
                                       confidence=0.03, supporting=[], weakening=weak, created_at=_ts(opened, 8)))
            audit("agent", "diagnosis_complete", _ts(opened, 9), inc.id,
                  {"source": "playbook", "top_cause": sc["cause"], "confidence": 0.91, "fallback_reason": "no model configured"})
            audit("agent", "state_changed", _ts(opened, 9), inc.id, {"from": "investigating", "to": "deciding"})

        t = 10.0
        executed_states = {"resolved": "done", "mitigated": "done", "escalated": "rolled_back"}
        for typ, target in sc["actions"]:
            spec = catalog[typ]
            needs_approval = spec.risk == "high"
            session.add(Action(incident_id=inc.id, type=typ, target=target, risk=spec.risk,
                               mode="approval" if needs_approval else spec.mode, state=executed_states[sc["state"]],
                               rollback=spec.rollback, approved_by=sc["approved_by"], created_at=_ts(opened, 9)))
            audit("policy", "policy_decision", _ts(opened, t), inc.id,
                  {"action": typ, "mode": "approval" if needs_approval else "auto"})
            if needs_approval:
                audit("policy", "state_changed", _ts(opened, t + 1), inc.id, {"from": "deciding", "to": "awaiting_approval"})
                audit("human", "approved", _ts(opened, t + 14), inc.id, {"action": typ, "operator": sc["approved_by"]})
                t += 15
            audit("executor", "action_executed", _ts(opened, t + 1), inc.id, {"action": typ, "target": target})
            t += 3

        for n, passed in enumerate(sc["verify"], start=1):
            session.add(Verification(incident_id=inc.id, run_number=n, passed=passed, ms=180 + n * 7,
                                     created_at=_ts(opened, t + n * 2)))
            audit("verifier", "verification_run", _ts(opened, t + n * 2), inc.id, {"run": n, "passed": passed})
        if sc["state"] == "escalated":
            audit("executor", "action_rolled_back", _ts(opened, t + 4), inc.id, {"action": sc["actions"][0][0]})
            session.add(Ticket(incident_id=inc.id, kind="escalation", note="verification failed on run 1; rolled back 1 action(s)"))
        if sc["state"] == "false_positive":
            audit("human", "state_changed", _ts(opened, terminal_s), inc.id, {"from": "investigating", "to": "false_positive"})
        else:
            audit("verifier" if sc["state"] != "escalated" else "verifier", "state_changed", _ts(opened, terminal_s),
                  inc.id, {"from": "verifying", "to": sc["state"]})
    session.commit()
    return counts


def remove_demo(session: Session) -> dict[str, int]:
    ids = list(session.scalars(select(Incident.id).where(Incident.is_demo.is_(True))))
    for model in (Evidence, Hypothesis, Action, Verification, Ticket):
        session.execute(delete(model).where(model.incident_id.in_(ids)))
    session.execute(delete(AuditEvent).where(AuditEvent.is_demo.is_(True)))
    session.execute(delete(JourneyRun).where(JourneyRun.is_demo.is_(True)))
    session.execute(delete(Incident).where(Incident.is_demo.is_(True)))
    session.commit()
    return {"incidents": len(ids)}


if __name__ == "__main__":  # python -m app.demo.seed
    from app.core.db import get_sessionmaker

    with get_sessionmaker()() as s:
        print(seed_demo(s))
