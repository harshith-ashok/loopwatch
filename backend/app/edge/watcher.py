"""Background loops: tick the simulator, and evaluate edge detector rules."""
import asyncio
import logging

from app.agents.dispatch import announce_opened
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.detector.engine import evaluate_edge
from app.edge.simulator import sim
from app.edge.store import store

log = logging.getLogger("edge")


def sim_tick() -> None:
    """One simulator tick through the same ingest path a real board's POST would use."""
    msg = sim.step()
    if msg is not None:
        sim.handle_commands(store.ingest(msg))


def watch_once() -> None:
    with get_sessionmaker()() as session:
        for incident in evaluate_edge(session):
            announce_opened(incident)


class EdgeRunner:
    def __init__(self) -> None:
        self._tasks: list[asyncio.Task[None]] = []

    def start(self) -> None:
        if self._tasks:
            return
        cfg = get_settings()
        if cfg.edge_sim_enabled:
            self._tasks.append(asyncio.create_task(self._loop(sim_tick, cfg.edge_tick_s), name="edge-sim"))
        self._tasks.append(asyncio.create_task(self._loop(watch_once, cfg.edge_watch_s), name="edge-watch"))

    @staticmethod
    async def _loop(fn, interval: float) -> None:  # noqa: ANN001
        while True:
            try:
                fn()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("edge loop error")
            await asyncio.sleep(interval)

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []


edge_runner = EdgeRunner()
