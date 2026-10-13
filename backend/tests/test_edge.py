import asyncio
import json
import time
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.detector import rules
from app.detector.engine import evaluate_edge
from app.edge.simulator import BOOT_TICKS, EdgeSimulator, sim
from app.edge.store import store
from app.edge.watcher import sim_tick, watch_once
from app.journeys.runner import runner
from app.models.journeys import Incident
from app.models.ops import FaultRun
from app.schemas.edge import TelemetryMessage
from app.shop.faults import state

SAMPLE = json.loads((Path(__file__).parent / "contracts" / "edge_message.json").read_text())
NODE = SAMPLE["node"]


def incidents() -> list[Incident]:
    with get_sessionmaker()() as s:
        return list(s.scalars(select(Incident).order_by(Incident.id)))


def feed(simulator: EdgeSimulator, ticks: int, t0: float = 1000.0, step: float = 2.0) -> float:
    """Run the simulator and ingest with a fake clock. Returns the clock after the last tick."""
    t = t0
    for _ in range(ticks):
        t += step
        msg = simulator.step()
        if msg is not None:
            store.ingest(msg, now=t)
    return t


# ---- schema: simulator and a real board are indistinguishable -------------------------------

def test_simulator_and_board_share_one_schema() -> None:
    board = TelemetryMessage.model_validate(SAMPLE)  # what the firmware is documented to send
    msg = EdgeSimulator(seed=1).step()
    assert msg is not None
    assert set(msg.model_dump()) == set(board.model_dump()) == set(SAMPLE)
    assert msg.fault is None and msg.node == NODE


@pytest.mark.parametrize(
    "patch",
    [{"temp_c": 999}, {"rssi_dbm": 5}, {"fan_rpm": -1}, {"node": ""}, {"node": "bad node!"}, {"uptime_s": -3}],
)
def test_malformed_telemetry_is_rejected(client, patch) -> None:
    r = client.post("/api/v1/edge/telemetry", json={**SAMPLE, **patch})
    assert r.status_code == 422
    assert client.get("/api/v1/edge/status").json()["seen"] is False


def test_missing_field_is_rejected(client) -> None:
    body = {k: v for k, v in SAMPLE.items() if k != "temp_c"}
    assert client.post("/api/v1/edge/telemetry", json=body).status_code == 422


# ---- simulator behaviour ---------------------------------------------------------------------

def test_normal_mode_stays_healthy() -> None:
    s = EdgeSimulator(seed=2)
    for _ in range(40):
        m = s.step()
        assert m and 35 < m.temp_c < 48 and m.fan_rpm > 3900 and -70 < m.rssi_dbm < -45


def test_overheat_stalls_fan_and_crosses_limit() -> None:
    s = EdgeSimulator(seed=3)
    s.set_mode("overheat")
    msgs = [s.step() for _ in range(10)]
    assert msgs[-1].fan_rpm == 0
    assert any(m.temp_c > 70 for m in msgs)
    assert msgs[-1].temp_c <= 88  # capped


def test_dropping_degrades_rssi_then_goes_silent() -> None:
    s = EdgeSimulator(seed=4)
    s.set_mode("dropping")
    rssi = [s.step().rssi_dbm for _ in range(3)]
    assert rssi == sorted(rssi, reverse=True) and rssi[-1] < -80
    assert s.mode == "offline" and s.step() is None


def test_power_cycle_resets_uptime_but_does_not_fix_a_broken_fan() -> None:
    s = EdgeSimulator(seed=5)
    s.set_mode("overheat")
    for _ in range(6):
        s.step()
    s.handle_commands(["power_cycle"])
    assert [s.step() for _ in range(BOOT_TICKS)] == [None] * BOOT_TICKS
    m = s.step()
    assert m.uptime_s < 10 and s.mode == "overheat" and m.fan_rpm == 0


def test_restore_returns_to_normal() -> None:
    s = EdgeSimulator(seed=6)
    s.set_mode("overheat")
    for _ in range(8):
        s.step()
    s.restore()
    last = None
    for _ in range(12):
        last = s.step()
    assert s.mode == "normal" and last.temp_c < 50 and last.fan_rpm > 3900


# ---- detector rules --------------------------------------------------------------------------

def test_overheat_rule_needs_the_limit_held() -> None:
    hot = [(t, 75.0) for t in (0, 2, 4, 6, 8, 10)]
    assert rules.overheat(hot, 70, 10).rule == "temperature_limit"
    assert rules.overheat(hot[:5], 70, 10) is None  # only 8 s so far
    blip = [(0, 75.0), (2, 75.0), (4, 60.0), (6, 75.0), (8, 75.0), (10, 75.0)]
    assert rules.overheat(blip, 70, 10) is None  # dipped below: the hold restarts
    assert rules.overheat([], 70, 10) is None


def test_heartbeat_rule_is_three_missed_beats() -> None:
    assert rules.heartbeat_missed(5.9, 2, 3) is None
    assert rules.heartbeat_missed(6.1, 2, 3).rule == "heartbeat_missed"
    assert rules.heartbeat_missed(None, 2, 3) is None  # never seen is not "missed"


def test_control_run_no_edge_incident(client) -> None:
    s = EdgeSimulator(seed=7)
    t = feed(s, 60)
    with get_sessionmaker()() as session:
        assert evaluate_edge(session, now=t) == []
    assert incidents() == []


def test_overheat_opens_exactly_one_incident(client) -> None:
    s = EdgeSimulator(seed=8)
    t = feed(s, 5)
    s.set_mode("overheat")
    opened_at_tick = None
    for i in range(1, 20):
        t = feed(s, 1, t0=t)
        with get_sessionmaker()() as session:
            if evaluate_edge(session, now=t) and opened_at_tick is None:
                opened_at_tick = i
    assert opened_at_tick is not None
    found = incidents()
    assert len(found) == 1
    assert found[0].rule == "temperature_limit" and found[0].journey == "edge" and found[0].dedupe_key == "device"
    assert found[0].signals["count"] > 1


def test_link_loss_opens_one_incident_after_three_missed_beats(client) -> None:
    s = EdgeSimulator(seed=9)
    t = feed(s, 5)
    s.set_mode("dropping")
    t = feed(s, 3, t0=t)  # three degraded messages, then silence
    last_message_at = t
    assert s.mode == "offline"
    with get_sessionmaker()() as session:
        assert evaluate_edge(session, now=last_message_at + 5.9) == []
        assert len(evaluate_edge(session, now=last_message_at + 6.5)) == 1
        assert evaluate_edge(session, now=last_message_at + 9) == []  # debounced
    assert [i.rule for i in incidents()] == ["heartbeat_missed"]


# ---- API, store and commands ----------------------------------------------------------------

def test_status_and_history(client) -> None:
    assert client.get("/api/v1/edge/status").json()["seen"] is False
    for _ in range(5):
        sim_tick()
    body = client.get("/api/v1/edge/status").json()
    assert body["seen"] and body["online"] and body["node"] == NODE
    assert len(body["history"]) == 5 and body["temp_limit_c"] == 70
    assert set(body["latest"]) == set(SAMPLE)


def test_command_queue_is_delivered_once(client) -> None:
    store.enqueue_command(NODE, "power_cycle")
    r = client.post("/api/v1/edge/telemetry", json=SAMPLE).json()
    assert r == {"accepted": True, "commands": ["power_cycle"]}
    assert client.post("/api/v1/edge/telemetry", json=SAMPLE).json()["commands"] == []
    with pytest.raises(ValueError):
        store.enqueue_command(NODE, "format_disk")  # only catalog-known commands


def test_simulator_receives_power_cycle_through_the_same_path(client) -> None:
    for _ in range(3):
        sim_tick()
    before = sim.uptime_s
    store.enqueue_command(NODE, "power_cycle")
    sim_tick()  # ingest returns the command, simulator reboots
    assert sim.power_cycles == 1 and sim.uptime_s < before


# ---- faults and hub acknowledgement ---------------------------------------------------------

def test_fault_endpoints_drive_the_simulator(client) -> None:
    r = client.post("/api/v1/faults/overheat").json()
    assert r["true_cause"] == "cooling_fault" and sim.mode == "overheat"
    r = client.post("/api/v1/faults/link").json()
    assert r["true_cause"] == "link_lost" and sim.mode == "dropping"
    with get_sessionmaker()() as s:
        assert {f.scenario for f in s.scalars(select(FaultRun))} == {"overheat", "link"}
    client.post("/api/v1/faults/reset")
    assert sim.mode == "normal"


async def order_run(client):
    return await runner.run_once("order", client.app)


async def test_ack_passes_with_a_healthy_hub(client) -> None:
    sim_tick()
    result = await order_run(client)
    assert result.ok and result.steps[-1].id == "ack" and result.steps[-1].status == "ok"


async def test_ack_fails_when_hub_offline_and_manual_route_mitigates(client, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "edge_tick_s", 0.05)
    client.post("/api/v1/faults/link")
    for _ in range(4):
        sim_tick()
    await asyncio.sleep(0.25)  # > 3 missed beats at 0.05 s
    result = await order_run(client)
    assert not result.ok and result.failed_step == "ack"
    assert result.steps[-1].error_kind == "device_offline"

    # Fallback: acks go to the manual queue. The journey works though the device stays down.
    state.ack_route = "manual"  # what the switch_endpoint action will flip in Phase 6
    result = await order_run(client)
    assert result.ok
    assert sim.mode == "offline"


async def test_ack_is_slow_when_hub_is_hot(client) -> None:
    sim_tick()
    client.post("/api/v1/faults/overheat")
    for _ in range(8):
        sim_tick()
    result = await order_run(client)
    ack = result.steps[-1]
    assert result.ok and ack.id == "ack" and ack.ms >= get_settings().shop_ack_hot_slow_ms


async def test_link_fault_end_to_end_opens_one_device_incident(client, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "edge_tick_s", 0.05)
    for _ in range(3):
        sim_tick()
    client.post("/api/v1/faults/link")
    for _ in range(4):
        sim_tick()
    await asyncio.sleep(0.25)
    await order_run(client)  # ack step failure
    watch_once()  # heartbeat rule
    await order_run(client)
    watch_once()
    found = incidents()
    assert len(found) == 1, [(i.rule, i.dedupe_key) for i in found]
    assert found[0].dedupe_key == "device"
    assert set(found[0].signals["rules_seen"]) == {"step_failure", "heartbeat_missed"}


def test_reset_leaves_the_node_healthy_and_does_not_reopen_an_incident(client) -> None:
    client.post("/api/v1/faults/overheat")
    t = time.time()
    for _ in range(14):  # ramp takes ~5 ticks to cross 70 C, then 10 s hold
        store.ingest(sim.step(), now=t)
        t += 2
    with get_sessionmaker()() as session:
        assert evaluate_edge(session, now=t)
    client.post("/api/v1/faults/reset")
    status = client.get("/api/v1/edge/status").json()
    assert status["online"] and status["temp_c"] < 50 and status["fan_rpm"] > 3900
    assert status["history"] and all(h["temp_c"] < 50 for h in status["history"])  # no pre-reset readings
    with get_sessionmaker()() as session:
        assert evaluate_edge(session) == []
    assert [i.state for i in incidents()] == ["cancelled"]
