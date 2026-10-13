import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.core.incident_machine import IllegalTransition, add_evidence, transition
from app.models.incidents import Action, Hypothesis, Verification
from app.models.journeys import Incident
from app.models.ops import AuditEvent
from app.schemas.incidents import IncidentDetail

CONTRACT = Path(__file__).parent / "contracts" / "incident_detail.json"


def make_incident(session) -> Incident:
    inc = Incident(title="t", journey="order", rule="step_failure", dedupe_key="confirm", signals={})
    session.add(inc)
    session.commit()
    return inc


FREE_FORM = {"signals", "detail", "args", "result"}  # open-ended by design; contents not pinned


def shape(value):
    """Recursive key structure: dict keys and the shape of the first list element."""
    if isinstance(value, dict):
        return {k: ("object" if k in FREE_FORM else shape(v)) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    return type(value).__name__ if value is not None else "null"


def test_full_lifecycle_writes_audit_for_each_transition(client) -> None:
    with get_sessionmaker()() as s:
        inc = make_incident(s)
        for new, actor in [
            ("deciding", "agent"),
            ("awaiting_approval", "policy"),
            ("acting", "human"),
            ("verifying", "executor"),
        ]:
            transition(s, inc, new, actor)
        with pytest.raises(IllegalTransition):
            transition(s, inc, "resolved", "verifier")  # no verifications yet
        s.add_all([Verification(incident_id=inc.id, run_number=n, passed=True, ms=5) for n in (1, 2, 3)])
        s.commit()
        transition(s, inc, "resolved", "verifier")
        assert inc.state == "resolved" and inc.closed_at is not None
        events = s.scalars(select(AuditEvent).where(AuditEvent.incident_id == inc.id)).all()
    assert [(e.actor, e.detail["to"]) for e in events] == [
        ("agent", "deciding"),
        ("policy", "awaiting_approval"),
        ("human", "acting"),
        ("executor", "verifying"),
        ("verifier", "resolved"),
    ]


def test_illegal_transitions_are_rejected(client) -> None:
    with get_sessionmaker()() as s:
        inc = make_incident(s)
        with pytest.raises(IllegalTransition):
            transition(s, inc, "resolved", "verifier")  # cannot skip acting and verifying
        transition(s, inc, "cancelled", "human")
        with pytest.raises(IllegalTransition):
            transition(s, inc, "deciding", "agent")  # terminal is final


def test_evidence_refs_increment_per_incident(client) -> None:
    with get_sessionmaker()() as s:
        a, b = make_incident(s), make_incident(s)
        assert [add_evidence(s, a.id, "logs.search", {}, {}).ref for _ in range(3)] == ["E1", "E2", "E3"]
        assert add_evidence(s, b.id, "logs.search", {}, {}).ref == "E1"


def test_incident_detail_payload_matches_contract(client) -> None:
    with get_sessionmaker()() as s:
        inc = make_incident(s)
        add_evidence(s, inc.id, "detector.signal", {"rule": "step_failure"}, {"summary": "x"})
        s.add(Hypothesis(incident_id=inc.id, rank=1, cause="c", cause_key="worker_stalled", confidence=0.9, supporting=["E1"], weakening=[]))
        s.add(Action(incident_id=inc.id, type="restart_service", target="order-worker", risk="medium",
                     mode="auto", state="awaiting_approval", rollback="Redeploy previous revision"))
        s.add(Verification(incident_id=inc.id, run_number=1, passed=True, ms=10))
        s.commit()
        transition(s, inc, "deciding", "agent")
        incident_id = inc.id

    body = client.get(f"/api/v1/incidents/{incident_id}").json()
    expected = json.loads(CONTRACT.read_text())
    IncidentDetail.model_validate(expected)  # the checked-in sample is itself valid
    assert shape(body) == shape(expected)
    assert body["stage"] == "decide" and body["state"] == "deciding"
    assert client.get("/api/v1/incidents/9999").status_code == 404


def test_list_shape_has_no_child_collections(client) -> None:
    with get_sessionmaker()() as s:
        make_incident(s)
    row = client.get("/api/v1/incidents").json()[0]
    assert set(row) == {"id", "title", "journey", "state", "stage", "failed_stage", "rule", "signals", "opened_at", "closed_at", "is_demo", "top_cause", "pending_action"}
