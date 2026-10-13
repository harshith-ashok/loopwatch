"""Four specialists. Each owns a fixed set of read-only tools; the plan is deterministic
(fixed tool order), which keeps demo runs repeatable."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.models.journeys import Incident

ToolCall = tuple[str, dict[str, Any]]


@dataclass(frozen=True)
class Specialist:
    name: str
    plan: Callable[[Incident], list["ToolCall"]]


def _transactions(i: Incident) -> list[ToolCall]:
    return [("db.payments", {"incident_id": i.id}), ("db.orders", {}), ("traces.slowest", {})]


def _app_logs(i: Incident) -> list[ToolCall]:
    return [("metrics.queue_depth", {}), ("logs.search", {"limit": 15})]


def _device(i: Incident) -> list[ToolCall]:
    return [("device.health", {}), ("device.telemetry", {"n": 10}), ("network.ping", {})]


def _past(i: Incident) -> list[ToolCall]:
    return [("memory.similar", {"query": i.title, "k": 3})]


SPECIALISTS: list[Specialist] = [
    Specialist("transactions", _transactions),
    Specialist("app_and_logs", _app_logs),
    Specialist("device", _device),
    Specialist("past_incidents", _past),
]
