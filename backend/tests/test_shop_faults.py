import random
import time

from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models.ops import AuditEvent, FaultRun
from app.models.shop import ShopLog
from app.shop import routes
from app.shop.seed import DEMO_EMAIL, DEMO_PASSWORD


def journey(client, route: str = "/shop/pay") -> tuple[int, int]:
    """login -> cart -> checkout -> payment. Returns (payment status code, order id)."""
    token = client.post("/shop/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}).json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    assert client.post("/shop/cart/items", json={"product_id": 1}, headers=auth).status_code == 200
    order_id = client.post("/shop/checkout", headers=auth).json()["order_id"]
    return client.post(route, json={"order_id": order_id}).status_code, order_id


def wait_status(client, order_id: int, want: str, timeout: float = 1.0) -> str:
    deadline = time.time() + timeout
    status = ""
    while time.time() < deadline:
        status = client.get(f"/shop/orders/{order_id}").json()["status"]
        if status == want:
            break
        time.sleep(0.01)
    return status


def test_healthy_shop_completes_the_journey(client) -> None:
    code, order_id = journey(client)
    assert code == 200
    assert wait_status(client, order_id, "confirmed") == "confirmed"
    shop = client.get("/shop/state").json()
    assert shop["consumers"] == 1 and shop["queue_depth"] == 0


def test_bad_login_is_rejected(client) -> None:
    r = client.post("/shop/login", json={"email": DEMO_EMAIL, "password": "nope"})
    assert r.status_code == 401


def test_stall_leaves_paid_orders_pending_until_reset(client) -> None:
    assert client.post("/api/v1/faults/stall").status_code == 200
    code, order_id = journey(client)
    assert code == 200  # payment still captures; the symptom is downstream
    time.sleep(0.1)
    assert client.get(f"/shop/orders/{order_id}").json()["status"] == "paid"
    shop = client.get("/shop/state").json()
    assert shop["consumers"] == 0 and shop["queue_depth"] == 1

    assert client.post("/api/v1/faults/reset").status_code == 200
    assert wait_status(client, order_id, "confirmed") == "confirmed"


def test_timeout_degrades_primary_only(client) -> None:
    routes._rng = random.Random(7)
    client.post("/api/v1/faults/timeout")
    codes = [journey(client, "/shop/payments-primary/charge")[0] for _ in range(60)]
    error_rate = codes.count(504) / len(codes)
    assert 0.05 < error_rate < 0.45, error_rate
    assert set(codes) <= {200, 504}
    # Fallback gateway is unaffected while primary is degraded.
    assert all(journey(client, "/shop/payments-fallback/charge")[0] == 200 for _ in range(10))
    with get_sessionmaker()() as s:
        events = s.scalars(select(ShopLog.event)).all()
    assert "gateway_timeout" in events and "payment_captured" in events


def test_fault_runs_hold_ground_truth_and_reset_clears(client) -> None:
    r = client.post("/api/v1/faults/stall").json()
    assert r["true_cause"] == "worker_stalled"
    client.post("/api/v1/faults/timeout")
    with get_sessionmaker()() as s:
        runs = s.scalars(select(FaultRun)).all()
        assert {x.scenario: x.true_cause for x in runs} == {
            "stall": "worker_stalled",
            "timeout": "gateway_degraded",
        }
        assert all(x.injected_at and x.cleared_at is None for x in runs)
    client.post("/api/v1/faults/reset")
    with get_sessionmaker()() as s:
        assert all(x.cleared_at is not None for x in s.scalars(select(FaultRun)))
        actions = [e.action for e in s.scalars(select(AuditEvent).order_by(AuditEvent.id))]
    assert actions == ["fault_injected", "fault_injected", "faults_reset"]
    assert client.get("/shop/state").json()["faults"] == {"stall": False, "timeout": False}


def test_unknown_and_unimplemented_scenarios(client) -> None:
    assert client.post("/api/v1/faults/bogus").status_code == 404
    assert client.post("/api/v1/faults/overheat").status_code == 200
