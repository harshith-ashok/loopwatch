import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.core.config import get_settings
from app.core.events import bus

router = APIRouter()


@router.get("/events")
async def events() -> EventSourceResponse:
    queue = bus.subscribe()
    interval = get_settings().sse_heartbeat_s

    async def stream() -> AsyncIterator[dict[str, str]]:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=interval)
                except asyncio.TimeoutError:
                    bus.publish("heartbeat", {"subscribers": bus.subscriber_count})
                    continue
                yield {"event": event["type"], "data": json.dumps(event)}
        finally:
            bus.unsubscribe(queue)

    return EventSourceResponse(stream())
