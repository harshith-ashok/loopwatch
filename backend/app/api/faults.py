from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import get_session
from app.core.incident_machine import transition
from app.models.journeys import TERMINAL_STATES, Incident
from app.models.ops import FaultRun
from app.core.config import get_settings
from app.detector.engine import clear_suppression
from app.edge.simulator import sim
from app.edge.store import store
from app.edge.watcher import sim_tick
from app.shop.faults import state
from app.shop.logs import shop_log
from app.shop.worker import worker

router = APIRouter(prefix="/faults", tags=["faults"])

TRUE_CAUSE = {
    "stall": "worker_stalled",
    "timeout": "gateway_degraded",
    "overheat": "cooling_fault",
    "link": "link_lost",
    "decoy": "none",  # slow but healthy dependency: ground truth is "no fault"
}
IMPLEMENTED = {"stall", "timeout", "overheat", "link", "decoy"}
SIM_MODE = {"overheat": "overheat", "link": "dropping"}

Db = Annotated[Session, Depends(get_session)]


def _clear_open_runs(session: Session) -> None:
    now = datetime.now(timezone.utc)
    for run in session.scalars(select(FaultRun).where(FaultRun.cleared_at.is_(None))):
        run.cleared_at = now
    session.commit()


@router.post("/reset")
def reset(session: Db) -> dict[str, object]:
    state.reset()
    sim.hard_reset()
    if get_settings().edge_sim_enabled:
        # Drop the old history and publish a healthy reading at once, so readings from the
        # previous scenario are neither the latest sample nor evidence for the next diagnosis.
        store.clear_node(get_settings().edge_node)
        sim_tick()
    _clear_open_runs(session)
    worker.start()
    # A reset cancels open incidents; otherwise a stale incident would swallow the next
    # injection via debounce. Two passes: the watcher runs on another thread and can open an
    # incident between the first pass and the healthy reading becoming the latest sample.
    clear_suppression()
    for _ in range(2):
        for inc in list(session.scalars(select(Incident).where(Incident.state.not_in(TERMINAL_STATES)))):
            transition(session, inc, "cancelled", "harness", "faults reset")
    shop_log("faults", "faults_reset", "all fault switches cleared")
    audit.record(session, "harness", "faults_reset")
    return {"ok": True}


@router.post("/{scenario}")
def inject(scenario: str, session: Db) -> dict[str, object]:
    if scenario not in TRUE_CAUSE:
        raise HTTPException(404, f"unknown scenario: {scenario}")
    if scenario not in IMPLEMENTED:
        raise HTTPException(501, f"scenario '{scenario}' needs the edge node (Phase 4)")
    if scenario in SIM_MODE:
        sim.set_mode(SIM_MODE[scenario])
    else:
        setattr(state, "slow" if scenario == "decoy" else scenario, True)
    run = FaultRun(scenario=scenario, true_cause=TRUE_CAUSE[scenario])
    session.add(run)
    session.commit()
    shop_log("faults", "fault_injected", f"fault injected: {scenario}", level="WARNING", scenario=scenario)
    audit.record(session, "harness", "fault_injected", {"scenario": scenario, "fault_run_id": run.id})
    return {"fault_run_id": run.id, "scenario": scenario, "true_cause": run.true_cause}
