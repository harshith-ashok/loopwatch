"""Read-only investigation tools (hard rule 3). Nothing here writes; the test suite asserts it.
Results are plain data. Free text inside them (log messages) is untrusted (hard rule 7)."""
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import fmean
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.embedding import cosine, embed
from app.core.config import get_settings
from app.edge.store import store
from app.models.incidents import PastIncident
from app.models.journeys import Incident, JourneyRun
from app.models.shop import Payment, ShopLog, ShopOrder
from app.shop.worker import worker

MAX_TEXT = 200


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    run: Callable[[Session, dict[str, Any]], dict[str, Any]]


def _age_s(ts: datetime | None) -> float | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - ts).total_seconds(), 1)


def logs_search(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query", ""))[:80]
    limit = min(int(args.get("limit", 15)), 50)
    q = select(ShopLog).order_by(ShopLog.id.desc()).limit(limit)
    if args.get("component"):
        q = q.where(ShopLog.component == str(args["component"]))
    if query:
        like = f"%{query}%"
        q = q.where(ShopLog.event.ilike(like) | ShopLog.message.ilike(like))
    rows = list(session.scalars(q))
    return {
        "count": len(rows),
        "matches": [
            {"component": r.component, "level": r.level, "event": r.event, "message": r.message[:MAX_TEXT]}
            for r in rows
        ],
    }


def metrics_queue_depth(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    oldest = session.scalar(
        select(func.min(Payment.created_at))
        .join(ShopOrder, ShopOrder.id == Payment.order_id)
        .where(ShopOrder.status == "paid")
    )
    pending = session.scalar(select(func.count()).select_from(ShopOrder).where(ShopOrder.status == "paid"))
    return {
        "queue_depth": worker.queue_depth,
        "consumers": worker.consumers,
        "paid_unconfirmed_orders": pending or 0,
        "oldest_paid_unconfirmed_age_s": _age_s(oldest),
    }


def traces_slowest(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    runs = list(session.scalars(select(JourneyRun).where(JourneyRun.is_demo.is_(False)).order_by(JourneyRun.id.desc()).limit(int(args.get("runs", 60)))))
    steps: dict[str, dict[str, Any]] = {}
    for r in runs:
        for s in r.steps:
            if s["status"] == "skipped":
                continue
            agg = steps.setdefault(s["id"], {"ms": [], "failures": 0, "kinds": set()})
            agg["ms"].append(s["ms"])
            if s["status"] == "failed":
                agg["failures"] += 1
                agg["kinds"].add(s.get("error_kind") or "unknown")
    out = [
        {
            "step": k,
            "runs": len(v["ms"]),
            "mean_ms": round(fmean(v["ms"]), 1),
            "max_ms": max(v["ms"]),
            "failures": v["failures"],
            "error_kinds": sorted(v["kinds"]),
        }
        for k, v in steps.items()
    ]
    out.sort(key=lambda x: x["mean_ms"], reverse=True)
    return {"runs_examined": len(runs), "steps": out[:6]}


def db_orders(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    rows = session.execute(select(ShopOrder.status, func.count()).group_by(ShopOrder.status)).all()
    return {"by_status": {status: n for status, n in rows}}


def db_payments(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    """Payment outcomes per gateway over the last `since_s` seconds. Time-windowed so that
    failures from an earlier, already-handled fault are not read as the current one."""
    since_s = float(args.get("since_s", 20))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=since_s)
    # Failures from before the previous incident closed were already handled; they must not be
    # read as evidence for this one (it caused misdiagnoses when faults were injected back to back).
    prev_closed = session.scalar(
        select(func.max(Incident.closed_at)).where(
            Incident.closed_at.is_not(None),
            Incident.id != int(args.get("incident_id", -1)),
            Incident.is_demo.is_(False),
        )
    )
    if prev_closed is not None:
        if prev_closed.tzinfo is None:
            prev_closed = prev_closed.replace(tzinfo=timezone.utc)
        cutoff = max(cutoff, prev_closed)
    recent = list(
        session.scalars(
            select(Payment)
            .where(Payment.created_at >= cutoff)
            .order_by(Payment.id.desc())
            .limit(int(args.get("limit", 60)))
        )
    )
    out: dict[str, dict[str, Any]] = {}
    for gateway in ("primary", "fallback"):
        rows = [p for p in recent if p.gateway == gateway]
        out[gateway] = {
            "count": len(rows),
            "captured": sum(1 for p in rows if p.status == "captured"),
            "failed": sum(1 for p in rows if p.status == "failed"),
            "mean_latency_ms": round(fmean([p.latency_ms for p in rows]), 1) if rows else None,
            "max_latency_ms": max((p.latency_ms for p in rows), default=None),
        }
    return {"window": len(recent), "since_s": since_s, "since_previous_incident_closed": prev_closed is not None, "gateways": out}


def device_telemetry(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    node = get_settings().edge_node
    n = min(int(args.get("n", 10)), 30)
    now = time.time()
    samples = store.samples(node)[-n:]
    return {
        "node": node,
        "samples": [
            {"age_s": round(now - r.at, 1), "temp_c": r.msg.temp_c, "rssi_dbm": r.msg.rssi_dbm, "fan_rpm": r.msg.fan_rpm}
            for r in samples
        ],
    }


def device_health(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    st = store.status(get_settings().edge_node)
    return st.model_dump(exclude={"history", "latest"})


def network_ping(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    """Reachability of the edge node, derived from its heartbeat (the node is simulated)."""
    st = store.status(get_settings().edge_node)
    return {
        "target": st.node,
        "reachable": st.online,
        "heartbeat_age_s": st.heartbeat_age_s,
        "basis": "heartbeat age; no ICMP is sent",
    }


def memory_similar(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    text = str(args.get("query", ""))[:400]
    k = min(int(args.get("k", 3)), 5)
    vec = embed(text)
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        rows = session.execute(
            select(PastIncident, PastIncident.embedding.cosine_distance(vec).label("d"))
            .order_by("d")
            .limit(k)
        ).all()
        scored = [(1.0 - float(d), p) for p, d in rows]
    else:
        scored = sorted(
            ((cosine(vec, list(p.embedding)), p) for p in session.scalars(select(PastIncident))),
            key=lambda x: x[0],
            reverse=True,
        )[:k]
    return {
        "matches": [
            {
                "similarity": round(sim, 3),
                "summary": p.summary[:MAX_TEXT],
                "cause_key": p.cause_key,
                "action": p.action,
                "outcome": p.outcome,
            }
            for sim, p in scored
        ]
    }


REGISTRY: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool("logs.search", "Search recent shop log lines by text and component.", logs_search),
        Tool("metrics.queue_depth", "Order queue depth, consumer count, paid-but-unconfirmed orders.", metrics_queue_depth),
        Tool("traces.slowest", "Slowest and failing journey steps over recent runs.", traces_slowest),
        Tool("db.orders", "Order counts by status.", db_orders),
        Tool("db.payments", "Payment outcomes and latency per gateway.", db_payments),
        Tool("device.telemetry", "Recent edge node telemetry samples.", device_telemetry),
        Tool("device.health", "Edge node status: online, heartbeat age, temperature, fan, signal.", device_health),
        Tool("network.ping", "Reachability of the edge node.", network_ping),
        Tool("memory.similar", "Past incidents most similar to a text query.", memory_similar),
    ]
}


def call_tool(session: Session, name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name not in REGISTRY:
        raise KeyError(f"unknown tool: {name}")
    return REGISTRY[name].run(session, args)
