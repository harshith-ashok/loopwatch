"""Order worker: consumes paid orders from a queue and confirms them."""
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.models.shop import ShopOrder
from app.shop.faults import state
from app.shop.logs import shop_log


class OrderWorker:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[int] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None

    @property
    def queue_depth(self) -> int:
        return self.queue.qsize()

    @property
    def consumers(self) -> int:
        """Active consumers. A stalled worker is alive but consumes nothing."""
        running = self._task is not None and not self._task.done()
        return 1 if running and not state.stall else 0

    def enqueue(self, order_id: int) -> None:
        self.queue.put_nowait(order_id)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self.queue = asyncio.Queue()  # bind to the running loop
            self._task = asyncio.create_task(self._run(), name="order-worker")
            shop_log("worker", "worker_started", "order worker started")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def restart(self) -> None:
        """What the restart_service action does: the worker comes back healthy."""
        state.stall = False
        self.start()
        shop_log("worker", "worker_restarted", "order worker restarted")

    def requeue_unconfirmed(self) -> int:
        """After a process restart, paid-but-unconfirmed orders go back on the queue."""
        with get_sessionmaker()() as session:
            ids = session.scalars(select(ShopOrder.id).where(ShopOrder.status == "paid")).all()
        for order_id in ids:
            self.enqueue(order_id)
        return len(ids)

    async def _run(self) -> None:
        tick = get_settings().shop_worker_tick_ms / 1000
        while True:
            if state.stall or self.queue.empty():
                await asyncio.sleep(tick)
                continue
            order_id = self.queue.get_nowait()
            await asyncio.sleep(tick)
            with get_sessionmaker()() as session:
                order = session.get(ShopOrder, order_id)
                if order and order.status == "paid":
                    order.status = "confirmed"
                    order.confirmed_at = datetime.now(timezone.utc)
                    session.commit()
                    shop_log("worker", "order_confirmed", f"order {order_id} confirmed", order_id=order_id)


worker = OrderWorker()
