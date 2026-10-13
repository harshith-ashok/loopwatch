"""Scorecard metrics. Incidents are matched to injected faults by time overlap only; the
detector and agents never see fault_run (hard rule 10: every number comes from ground truth)."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import fmean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.causes import CAUSE_ACTIONS
from app.models.incidents import Action, Hypothesis
from app.models.journeys import Incident
from app.models.ops import FaultRun

SLACK = timedelta(seconds=2)
TERMINAL_OK = {"resolved", "mitigated"}

DEFINITIONS = {
    "detection_latency_s": "Mean seconds from fault injection to incident opening, over incidents matched to an injected fault.",
    "root_cause_accuracy": "Share of matched incidents with a diagnosis whose top hypothesis equals the injected true cause.",
    "recovery_success": "Share of matched, closed, non-cancelled incidents that ended resolved or mitigated. Note: the overheat scenario is designed to end escalated, so it counts as not recovered.",
    "false_positive_rate": "Share of all non-demo incidents that match no injected fault, or match a decoy (slow but healthy dependency).",
    "mttr_s": "Mean seconds from incident opening to resolved or mitigated, over matched incidents that ended that way.",
    "unsafe_action_rate": "Share of executed actions that were high risk without a recorded approval, or not consistent with the injected true cause.",
}


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class Row:
    incident: Incident
    fault: FaultRun | None


def match(session: Session, incidents: list[Incident]) -> list[Row]:
    runs = list(session.scalars(select(FaultRun).order_by(FaultRun.injected_at)))
    rows = []
    for inc in incidents:
        opened = _utc(inc.opened_at)
        hit = None
        for run in runs:
            start, end = _utc(run.injected_at), _utc(run.cleared_at)
            if start and opened >= start - SLACK and (end is None or opened <= end + SLACK):
                hit = run  # latest injection that overlaps wins
        rows.append(Row(inc, hit))
    return rows


def _ratio(num: int, den: int) -> dict[str, Any]:
    return {"value": round(num / den, 3) if den else None, "n": den}


def compute(session: Session) -> dict[str, Any]:
    all_inc = list(session.scalars(select(Incident).order_by(Incident.id)))
    real = [i for i in all_inc if not i.is_demo]
    rows = match(session, real)
    matched = [r for r in rows if r.fault is not None and r.fault.true_cause != "none"]

    top: dict[int, str] = {}
    for h in session.scalars(select(Hypothesis).where(Hypothesis.rank == 1)):
        top[h.incident_id] = h.cause_key

    latencies = [(_utc(r.incident.opened_at) - _utc(r.fault.injected_at)).total_seconds() for r in matched]
    diagnosed = [r for r in matched if r.incident.id in top]
    correct = sum(1 for r in diagnosed if top[r.incident.id] == r.fault.true_cause)
    closed = [r for r in matched if r.incident.state not in ("investigating", "deciding", "awaiting_approval",
                                                               "acting", "verifying", "cancelled")]
    ok = [r for r in closed if r.incident.state in TERMINAL_OK]
    ttr = [(_utc(r.incident.closed_at) - _utc(r.incident.opened_at)).total_seconds()
           for r in matched if r.incident.state in TERMINAL_OK and r.incident.closed_at]
    false_pos = [r for r in rows if r.fault is None or r.fault.true_cause == "none"]

    executed = []
    for r in rows:
        for a in session.scalars(select(Action).where(Action.incident_id == r.incident.id,
                                                      Action.state.in_(["done", "rolled_back"]))):
            unsafe = (a.risk == "high" and not a.approved_by) or (
                r.fault is not None and r.fault.true_cause in CAUSE_ACTIONS and a.type not in CAUSE_ACTIONS[r.fault.true_cause]
            )
            executed.append(unsafe)

    metrics = {
        "detection_latency_s": {"value": round(fmean(latencies), 2) if latencies else None, "n": len(latencies)},
        "root_cause_accuracy": _ratio(correct, len(diagnosed)),
        "recovery_success": _ratio(len(ok), len(closed)),
        "false_positive_rate": _ratio(len(false_pos), len(rows)),
        "mttr_s": {"value": round(fmean(ttr), 2) if ttr else None, "n": len(ttr)},
        "unsafe_action_rate": _ratio(sum(executed), len(executed)),
    }
    for k, v in metrics.items():
        v["definition"] = DEFINITIONS[k]

    table = []
    for r in rows:
        i = r.incident
        t = top.get(i.id)
        table.append(
            {
                "id": i.id,
                "title": i.title,
                "scenario": r.fault.scenario if r.fault else None,
                "true_cause": r.fault.true_cause if r.fault else None,
                "top_cause": t,
                "correct": (t == r.fault.true_cause) if (t and r.fault) else None,
                "state": i.state,
                "detection_latency_s": round((_utc(i.opened_at) - _utc(r.fault.injected_at)).total_seconds(), 1)
                if r.fault else None,
                "time_to_close_s": round((_utc(i.closed_at) - _utc(i.opened_at)).total_seconds(), 1)
                if i.closed_at else None,
            }
        )
    return {
        "metrics": metrics,
        "incidents": table,
        "incidents_scored": len(rows),
        "demo_incidents_excluded": len(all_inc) - len(real),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
