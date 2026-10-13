"""Phase 6: the full detect -> investigate -> decide -> act -> verify loop, and the policy gates."""
import pytest
from sqlalchemy import select

from app.agents.dispatch import handle_incident
from app.core.db import get_sessionmaker
from app.executor import flow
from app.models.incidents import Action, Ticket
from app.models.journeys import Incident
from app.models.ops import AuditEvent
from test_agents import incidents, open_incident


def state_of(incident_id: int) -> str:
    with get_sessionmaker()() as s:
        return s.get(Incident, incident_id).state


def action_states(incident_id: int) -> dict[str, str]:
    with get_sessionmaker()() as s:
        return {a.type: a.state for a in s.scalars(select(Action).where(Action.incident_id == incident_id))}


def audit_actions(incident_id: int) -> list[tuple[str, str]]:
    with get_sessionmaker()() as s:
        rows = s.scalars(select(AuditEvent).where(AuditEvent.incident_id == incident_id).order_by(AuditEvent.id))
        return [(e.actor, e.action) for e in rows]


@pytest.mark.parametrize(
    "scenario,final,needs_approval",
    [("stall", "resolved", False), ("timeout", "resolved", False), ("overheat", "escalated", True), ("link", "mitigated", False)],
)
async def test_scenario_ends_in_the_expected_state(client, scenario, final, needs_approval) -> None:
    client.put("/api/v1/policy", json={"pace": "fast"})
    incident_id = await open_incident(client, scenario)
    await handle_incident(incident_id)

    if needs_approval:
        assert state_of(incident_id) == "awaiting_approval"
        assert action_states(incident_id) == {"power_cycle_device": "awaiting_approval"}
        assert await flow.approve(incident_id, "alice")
        await flow.proceed(incident_id)

    assert state_of(incident_id) == final
    log = audit_actions(incident_id)
    assert ("policy", "policy_decision") in log and ("executor", "action_executed") in log
    assert ("verifier", "verification_run") in log
    if final in ("resolved", "mitigated"):
        with get_sessionmaker()() as s:
            from app.models.incidents import Verification

            runs = list(s.scalars(select(Verification).where(Verification.incident_id == incident_id)))
        assert [r.passed for r in runs] == [True, True, True]  # three consecutive passes
    if scenario == "overheat":
        assert action_states(incident_id) == {"power_cycle_device": "rolled_back"}
        assert ("human", "approved") in log and ("executor", "action_rolled_back") in log
        with get_sessionmaker()() as s:
            assert s.scalar(select(Ticket).where(Ticket.incident_id == incident_id, Ticket.kind == "escalation"))


async def test_policy_gates_pause_deny_and_budget(client) -> None:
    client.put("/api/v1/policy", json={"pace": "fast"})

    # Pause switch: even a low-risk automatic action waits for a person.
    client.put("/api/v1/policy", json={"paused": True})
    inc1 = await open_incident(client, "stall")
    await handle_incident(inc1)
    assert state_of(inc1) == "awaiting_approval"
    # Denied approval escalates.
    assert await flow.deny(inc1, "bob")
    assert state_of(inc1) == "escalated" and action_states(inc1) == {"restart_service": "denied"}

    # Budget exhaustion escalates: link proposes two actions, budget allows one.
    client.post("/api/v1/faults/reset")
    client.put("/api/v1/policy", json={"paused": False, "budget": 1})
    inc2 = await open_incident(client, "link")
    await handle_incident(inc2)
    assert state_of(inc2) == "escalated"
    assert action_states(inc2) == {"switch_endpoint": "done", "open_ticket": "skipped"}

    # A high-risk action can never be set to automatic.
    r = client.put("/api/v1/policy", json={"modes": {"power_cycle_device": "auto"}})
    assert r.status_code == 422


async def test_escalated_fault_does_not_reopen_until_reset(client) -> None:
    """The node stays hot after an escalation; the detector must not spawn a new incident
    every second. A reset clears the cooldown so the next injection is detected."""
    from app.detector.engine import evaluate_edge

    client.put("/api/v1/policy", json={"pace": "fast"})
    first = await open_incident(client, "overheat")
    await handle_incident(first)
    await flow.approve(first, "alice")
    await flow.proceed(first)
    assert state_of(first) == "escalated"

    with get_sessionmaker()() as s:
        assert evaluate_edge(s) == []  # still hot, but it is the same escalated fault
    assert [i.id for i in incidents()] == [first]

    client.post("/api/v1/faults/reset")
    second = await open_incident(client, "overheat")
    assert second != first


async def test_resolved_incident_whose_fault_persists_does_not_flap(client) -> None:
    """A resolved incident must not spawn a new one a second later for the same signal."""
    from app.detector.engine import _handle
    from app.detector.rules import Signal

    client.put("/api/v1/policy", json={"pace": "fast"})
    first = await open_incident(client, "stall")
    await handle_incident(first)
    assert state_of(first) == "resolved"
    with get_sessionmaker()() as s:
        assert _handle(s, Signal("step_failure", "confirm", "again"), "order") is None  # suppressed
    assert [i.id for i in incidents()] == [first]
