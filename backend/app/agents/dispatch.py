"""Announce a newly opened incident and start its investigation in the background."""
import asyncio
import logging
from typing import Any

from app.core.config import get_settings
from app.core.events import bus

log = logging.getLogger("agents")
_tasks: set[asyncio.Task[Any]] = set()


def announce_opened(payload: dict[str, Any]) -> None:
    bus.publish("incident.opened", payload)
    if not get_settings().agents_enabled:
        return
    try:
        task = asyncio.get_running_loop().create_task(handle_incident(payload["id"]), name=f"incident-{payload['id']}")
    except RuntimeError:
        log.warning("no running loop; incident %s not investigated", payload["id"])
        return
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    task.add_done_callback(lambda t: t.cancelled() or t.exception() is None or log.error("investigation failed", exc_info=t.exception()))


def schedule(coro_fn, *args) -> None:  # noqa: ANN001
    """Run a coroutine in the background (used after an approval, so the request returns fast)."""
    task = asyncio.get_running_loop().create_task(coro_fn(*args))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def handle_incident(incident_id: int) -> None:
    """The whole pipeline for one incident, honouring the configured agent mode."""
    from app.agents.coordinator import investigate
    from app.core import audit
    from app.core.db import get_sessionmaker
    from app.core.incident_machine import transition
    from app.executor.flow import proceed
    from app.models.incidents import Action
    from app.models.journeys import Incident
    from app.policy.catalog import load_catalog
    from app.policy.engine import load_settings

    with get_sessionmaker()() as session:
        mode = load_settings(session).agent_mode

    if mode == "alert_only":
        with get_sessionmaker()() as session:
            audit.record(session, "policy", "alert_only", {"note": "baseline mode: no automated response"}, incident_id)
        return

    if mode == "blind_remediation":
        # Baseline: restart the worker on any alert, no investigation.
        with get_sessionmaker()() as session:
            inc = session.get(Incident, incident_id)
            if inc is None or inc.state != "investigating":
                return
            spec = load_catalog()["restart_service"]
            session.add(Action(incident_id=incident_id, type="restart_service", target="order-worker",
                               risk=spec.risk, mode=spec.mode, state="proposed", rollback=spec.rollback))
            session.commit()
            audit.record(session, "policy", "blind_remediation", {"action": "restart_service"}, incident_id)
            transition(session, inc, "deciding", "policy", "baseline: restart on any alert")
        await proceed(incident_id)
        return

    result = await investigate(incident_id)
    if result is not None and get_settings().agents_auto_act:
        await proceed(incident_id)
