import asyncio
import random
import time

import pytest
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.detector import rules
from app.edge.watcher import sim_tick
from app.journeys.definitions import JOURNEYS
from app.journeys.runner import runner
from app.models.journeys import Incident, JourneyRun
from app.models.ops import AuditEvent
from app.shop import routes


async def tick(client) -> None:
    """One simulator tick plus one pass of every journey, like one runner interval."""
    sim_tick()
    await asyncio.gather(*(runner.run_once(j, client.app) for j in JOURNEYS))


def incidents() -> list[Incident]:
    with get_sessionmaker()() as s:
        return list(s.scalars(select(Incident).order_by(Incident.id)))


async def test_control_run_opens_nothing(client) -> None:
    for _ in range(12):
        await tick(client)
    assert [(i.rule, i.title, i.signals) for i in incidents()] == []
    with get_sessionmaker()() as s:
        runs = list(s.scalars(select(JourneyRun)))
    assert len(runs) == 12 * len(JOURNEYS) and all(r.ok for r in runs)
    step_ids = [st["id"] for st in runs[0].steps]
    assert all(st["ms"] >= 0 and st["status"] == "ok" for st in runs[0].steps), step_ids


async def test_stall_opens_exactly_one_incident_quickly(client) -> None:
    for _ in range(3):
        await tick(client)
    client.post("/api/v1/faults/stall")
    t0 = time.monotonic()
    await tick(client)
    latency = time.monotonic() - t0
    assert latency < 2.0
    found = incidents()
    assert len(found) == 1
    inc = found[0]
    assert inc.rule == "step_failure" and inc.dedupe_key == "confirm" and inc.journey == "order"
    assert inc.state == "investigating"
    for _ in range(3):  # keeps failing, must not open more
        await tick(client)
    assert len(incidents()) == 1
    assert incidents()[0].signals["count"] > 1
    with get_sessionmaker()() as s:
        audit = list(s.scalars(select(AuditEvent).where(AuditEvent.action == "incident_opened")))
    assert len(audit) == 1 and audit[0].actor == "detector" and audit[0].incident_id == inc.id


async def test_timeout_opens_exactly_one_incident(client) -> None:
    routes._rng = random.Random(3)
    for _ in range(3):
        await tick(client)
    client.post("/api/v1/faults/timeout")
    ticks = 0
    while not incidents() and ticks < 15:
        await tick(client)
        ticks += 1
    assert ticks < 15, "timeout fault never detected"
    for _ in range(4):
        await tick(client)
    found = incidents()
    assert len(found) == 1, [(i.journey, i.dedupe_key) for i in found]
    assert found[0].dedupe_key == "pay" and found[0].rule == "step_failure"


async def test_reset_cancels_open_incident_so_next_fault_reopens(client) -> None:
    client.post("/api/v1/faults/stall")
    await tick(client)
    assert len(incidents()) == 1
    client.post("/api/v1/faults/reset")
    assert incidents()[0].state == "cancelled"
    client.post("/api/v1/faults/stall")
    await tick(client)
    assert len(incidents()) == 2


async def test_state_check_signal_from_paid_but_pending_orders(client) -> None:
    client.post("/api/v1/faults/stall")
    sim_tick()
    await runner.run_once("payment", client.app)  # pays, leaves order 'paid'
    await asyncio.sleep(1.2)  # past the 1 s test threshold
    await runner.run_once("login", client.app)
    inc = incidents()[0]
    assert "state_check" in inc.signals["rules_seen"] or inc.rule == "state_check"


def test_latency_rule_needs_both_slowness_and_timeouts() -> None:
    def run(ms, timeout=False):
        steps = [
            {"id": "pay", "label": "Charge card", "status": "failed" if timeout else "ok", "ms": ms,
             "error_kind": "timeout" if timeout else None}
        ]
        return {"total_ms": ms, "ok": not timeout, "steps": steps}

    base = [50, 52, 48, 51, 49, 50, 53, 47]
    kw = dict(min_runs=5, timeout_rate=0.15, sigma=3.0)
    slow_only = [run(1500) for _ in range(6)]
    assert rules.latency_degradation(slow_only, base, **kw) is None
    mixed = [run(1500)] * 4 + [run(3000, timeout=True)] * 2
    sig = rules.latency_degradation(mixed, base, **kw)
    assert sig and sig.rule == "latency_degradation" and sig.key == "pay"
    assert rules.latency_degradation(mixed[:3], base, **kw) is None  # too few runs
    assert rules.latency_degradation([run(50)] * 6, base, **kw) is None  # healthy


def test_journeys_api_and_overview(client) -> None:
    sim_tick()
    r = client.post("/api/v1/journeys/payment/run")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert client.post("/api/v1/journeys/nope/run").status_code == 404
    ov = client.get("/api/v1/overview").json()
    assert ov["journeys_total"] == 4 and ov["open_incidents"] == 0
    assert client.get("/api/v1/incidents").json() == []


@pytest.mark.parametrize("actor,n", [("detector", 0), ("harness", 0)])
def test_audit_filter(client, actor, n) -> None:
    assert client.get(f"/api/v1/audit?actor={actor}").status_code == 200
