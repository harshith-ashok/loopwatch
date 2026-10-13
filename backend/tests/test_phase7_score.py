"""Phase 7: scorecard metrics computed from ground truth, demo data excluded."""
from datetime import datetime, timedelta, timezone

from app.core.db import get_sessionmaker
from app.models.incidents import Action, Hypothesis
from app.models.journeys import Incident
from app.models.ops import FaultRun


def test_score_uses_ground_truth_and_excludes_demo(client) -> None:
    t0 = datetime.now(timezone.utc) - timedelta(minutes=10)
    with get_sessionmaker()() as s:
        runs = {
            "stall": FaultRun(scenario="stall", true_cause="worker_stalled", injected_at=t0, cleared_at=t0 + timedelta(seconds=60)),
            "overheat": FaultRun(scenario="overheat", true_cause="cooling_fault",
                                 injected_at=t0 + timedelta(minutes=2), cleared_at=t0 + timedelta(minutes=3)),
        }
        s.add_all(runs.values())

        def incident(opened, state, cause, closed=None, demo=False, action=None, approved=None, risk="medium"):
            i = Incident(title="t", journey="order", rule="step_failure", dedupe_key="k", signals={}, state=state,
                         opened_at=opened, closed_at=closed, is_demo=demo)
            s.add(i)
            s.flush()
            if cause:
                s.add(Hypothesis(incident_id=i.id, rank=1, cause="c", cause_key=cause, confidence=0.9))
            if action:
                s.add(Action(incident_id=i.id, type=action, target="x", risk=risk, mode="auto", state="done",
                             rollback="r", approved_by=approved))
            return i

        incident(t0 + timedelta(seconds=4), "resolved", "worker_stalled", t0 + timedelta(seconds=14),
                 action="restart_service")  # correct, resolved, 4 s, 10 s
        incident(t0 + timedelta(minutes=2, seconds=20), "escalated", "gateway_degraded",
                 t0 + timedelta(minutes=2, seconds=50), action="power_cycle_device", approved="alice", risk="high")
        incident(t0 + timedelta(minutes=8), "resolved", "worker_stalled", t0 + timedelta(minutes=8, seconds=5))  # no fault -> FP
        incident(t0 + timedelta(minutes=9), "resolved", "worker_stalled", demo=True)  # excluded
        s.commit()

    body = client.get("/api/v1/score").json()
    m = body["metrics"]
    assert body["incidents_scored"] == 3 and body["demo_incidents_excluded"] == 1
    assert m["detection_latency_s"] == {**m["detection_latency_s"], "value": 12.0, "n": 2}  # (4 + 20) / 2
    assert m["root_cause_accuracy"]["value"] == 0.5 and m["root_cause_accuracy"]["n"] == 2
    assert m["recovery_success"]["value"] == 0.5 and m["recovery_success"]["n"] == 2  # matched only: 1 resolved of 2
    assert m["false_positive_rate"]["value"] == 0.333
    assert m["mttr_s"]["value"] == 10.0 and m["mttr_s"]["n"] == 1  # the unmatched incident is not counted
    # power_cycle for a cooling fault is consistent and approved; restart for a stall is consistent.
    assert m["unsafe_action_rate"]["value"] == 0.0 and m["unsafe_action_rate"]["n"] == 2
    assert all("definition" in v for v in m.values())
