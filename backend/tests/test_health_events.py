import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.events import EventBus
from app.main import app


def test_health_reports_status() -> None:
    body = TestClient(app).get("/api/v1/health").json()
    assert body["status"] in {"ok", "degraded"}
    assert isinstance(body["db"], bool)


def test_cors_allows_vite_origin() -> None:
    r = TestClient(app).get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_bus_delivers_and_rejects_unknown() -> None:
    bus = EventBus()
    q = bus.subscribe()
    bus.publish("journey.updated", {"id": "login"})
    event = await asyncio.wait_for(q.get(), 1)
    assert event["type"] == "journey.updated" and event["data"] == {"id": "login"}
    with pytest.raises(ValueError):
        bus.publish("nope")
    bus.unsubscribe(q)
    assert bus.subscriber_count == 0
