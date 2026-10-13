"""In-process event bus. Publishers call publish(); each SSE client owns a queue."""
import asyncio
from datetime import datetime, timezone
from typing import Any

EVENT_TYPES = {
    "heartbeat",
    "journey.updated",
    "incident.opened",
    "incident.updated",
    "approval.requested",
    "edge.telemetry",
    "audit.appended",
}


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    def publish(self, type_: str, data: dict[str, Any] | None = None) -> None:
        if type_ not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {type_}")
        event = {"type": type_, "ts": datetime.now(timezone.utc).isoformat(), "data": data or {}}
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # slow client; drop rather than block the publisher

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


bus = EventBus()
