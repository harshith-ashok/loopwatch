"""Applies rules to stored runs and opens, or attaches to, incidents."""
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.incident_machine import add_evidence
from app.core.config import get_settings
from app.detector import rules
from app.detector.rules import Signal
from app.journeys.definitions import JOURNEYS
from app.models.journeys import TERMINAL_STATES, Incident, JourneyRun
from app.models.shop import Payment, ShopOrder


def _run_dict(r: JourneyRun) -> dict[str, Any]:
    return {"total_ms": r.total_ms, "ok": r.ok, "steps": r.steps}


def baseline_ms(session: Session, journey: str, before: datetime, n: int = 50) -> list[int]:
    """Rolling baseline: total_ms of the last n passing runs that predate the window."""
    return list(
        session.scalars(
            select(JourneyRun.total_ms)
            .where(and_(JourneyRun.journey == journey, JourneyRun.ok.is_(True), JourneyRun.is_demo.is_(False),
                       JourneyRun.started_at < before))
            .order_by(JourneyRun.started_at.desc())
            .limit(n)
        )
    )


def stuck_orders(session: Session, threshold_s: int) -> list[int]:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=threshold_s)
    return list(
        session.scalars(
            select(ShopOrder.id)
            .join(Payment, Payment.order_id == ShopOrder.id)
            .where(
                and_(ShopOrder.status == "paid", Payment.status == "captured", Payment.created_at < cutoff)
            )
        )
    )


# (dedupe key, rule) -> monotonic time until which a repeat signal is ignored. Set when an
# incident is escalated: a person has been told, and the same fault must not spawn a new
# incident every second. Cleared by the harness reset.
_SUPPRESSED: dict[tuple[str, str], float] = {}


_generation = 0  # bumped by every reset; an evaluation that straddles a reset is discarded


def suppress_reopen(key: str, rule: str) -> None:
    _SUPPRESSED[(key, rule)] = time.monotonic() + get_settings().detector_reopen_cooldown_s


def clear_suppression() -> None:
    global _generation
    _generation += 1
    _SUPPRESSED.clear()


def _open_incident(session: Session, key: str) -> Incident | None:
    return session.scalar(
        select(Incident).where(Incident.dedupe_key == key, Incident.state.not_in(TERMINAL_STATES))
    )


def _handle(session: Session, signal: Signal, journey: str, generation: int | None = None) -> dict[str, Any] | None:
    """Open an incident for a new key, or attach to the open one. Returns payload if opened."""
    if generation is not None and generation != _generation:
        return None  # a reset happened while this signal was being evaluated
    existing = _open_incident(session, signal.key)
    if existing is not None:
        sig = dict(existing.signals)
        sig["count"] = sig.get("count", 1) + 1
        sig["last_summary"] = signal.summary
        rules_seen = set(sig.get("rules_seen", [existing.rule]))
        rules_seen.add(signal.rule)
        sig["rules_seen"] = sorted(rules_seen)
        existing.signals = sig
        session.commit()
        return None

    if time.monotonic() < _SUPPRESSED.get((signal.key, signal.rule), 0.0):
        return None  # same ongoing fault, already escalated to a person

    label = JOURNEYS[journey]["label"] if journey in JOURNEYS else "Edge node"
    incident = Incident(
        title=f"{label}: {signal.summary}",
        journey=journey,
        rule=signal.rule,
        dedupe_key=signal.key,
        state="investigating",
        signals={
            "count": 1,
            "first_summary": signal.summary,
            "details": signal.details,
            "rules_seen": [signal.rule],
        },
    )
    session.add(incident)
    session.commit()
    audit.record(
        session,
        "detector",
        "incident_opened",
        {"rule": signal.rule, "key": signal.key, "summary": signal.summary, "details": signal.details},
        incident_id=incident.id,
    )
    add_evidence(
        session,
        incident.id,
        "detector.signal",
        {"rule": signal.rule, "key": signal.key},
        {"summary": signal.summary, **signal.details},
    )
    return {"id": incident.id, "title": incident.title, "journey": journey, "rule": signal.rule}


def evaluate(session: Session, journey: str, run: JourneyRun) -> list[dict[str, Any]]:
    cfg = get_settings()
    generation = _generation
    signals: list[Signal] = []

    s = rules.step_failure(run.failed_step, run.steps)
    if s:
        signals.append(s)

    window_start = datetime.now(timezone.utc) - timedelta(seconds=cfg.detector_window_s)
    window = [
        _run_dict(r)
        for r in session.scalars(
            select(JourneyRun).where(JourneyRun.journey == journey, JourneyRun.started_at >= window_start)
        )
    ]
    s = rules.latency_degradation(
        window,
        baseline_ms(session, journey, window_start),
        min_runs=cfg.detector_min_runs,
        timeout_rate=cfg.detector_timeout_rate,
        sigma=cfg.detector_sigma,
    )
    if s:
        signals.append(s)

    s = rules.state_check(stuck_orders(session, cfg.detector_state_check_s), cfg.detector_state_check_s)
    if s:
        signals.append(s)

    opened = []
    for signal in signals:
        payload = _handle(session, signal, journey, generation)
        if payload:
            opened.append(payload)
    return opened


def evaluate_edge(session: Session, now: float | None = None) -> list[dict[str, Any]]:
    """Edge rules: temperature limit and missed heartbeats. Run on a timer, not per journey run."""
    from app.edge.store import store  # local import: edge store depends on the event bus only

    cfg = get_settings()
    generation = _generation
    now = now if now is not None else time.time()
    node = cfg.edge_node
    samples = store.samples(node)
    signals: list[Signal] = []

    s = rules.overheat([(r.at, r.msg.temp_c) for r in samples], cfg.edge_temp_limit_c, cfg.edge_overheat_hold_s)
    if s:
        signals.append(s)
    age = (now - samples[-1].at) if samples else None
    s = rules.heartbeat_missed(age, cfg.edge_tick_s, cfg.edge_missed_beats)
    if s:
        signals.append(s)

    opened = []
    for signal in signals:
        payload = _handle(session, signal, "edge", generation)
        if payload:
            opened.append(payload)
    return opened
