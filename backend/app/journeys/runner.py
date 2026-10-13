"""Runs journeys as a customer would: HTTP calls, per-step status and timing."""
import asyncio
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI

from app.agents.dispatch import announce_opened
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.events import bus
from app.detector.engine import evaluate
from app.journeys.definitions import JOURNEYS, STEP_LABELS
from app.models.journeys import JourneyRun
from app.shop.seed import DEMO_EMAIL, DEMO_PASSWORD

log = logging.getLogger("journeys")


@dataclass
class StepResult:
    id: str
    label: str
    status: str  # ok | failed | skipped
    ms: int = 0
    error_kind: str | None = None  # timeout | http_error | stuck | exception
    detail: str | None = None


@dataclass
class RunResult:
    journey: str
    started_at: datetime
    ok: bool
    total_ms: int
    failed_step: str | None
    steps: list[StepResult]


class StepError(Exception):
    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind, self.detail = kind, detail


def _check(resp: httpx.Response) -> dict[str, Any]:
    if resp.status_code == 503:
        raise StepError("device_offline", "hub unreachable (503)")
    if resp.status_code == 504:
        raise StepError("timeout", "gateway timeout (504)")
    if resp.status_code >= 400:
        raise StepError("http_error", f"HTTP {resp.status_code}")
    return resp.json()


async def _do_step(step: str, client: httpx.AsyncClient, ctx: dict[str, Any]) -> None:
    cfg = get_settings()
    if step == "open_shop":
        _check(await client.get("/shop/products"))
    elif step == "login":
        body = _check(await client.post("/shop/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}))
        ctx["auth"] = {"Authorization": f"Bearer {body['token']}"}
    elif step == "add_to_cart":
        _check(await client.post("/shop/cart/items", json={"product_id": 1}, headers=ctx["auth"]))
    elif step == "checkout":
        ctx["order_id"] = _check(await client.post("/shop/checkout", headers=ctx["auth"]))["order_id"]
    elif step == "pay":
        _check(await client.post("/shop/pay", json={"order_id": ctx["order_id"]}))
    elif step == "confirm":
        deadline = time.monotonic() + cfg.journey_order_timeout_ms / 1000
        while True:
            status = _check(await client.get(f"/shop/orders/{ctx['order_id']}"))["status"]
            if status == "confirmed":
                return
            if time.monotonic() > deadline:
                raise StepError("stuck", f"order still '{status}' after {cfg.journey_order_timeout_ms} ms")
            await asyncio.sleep(0.05)
    elif step == "ack":
        _check(await client.post(f"/shop/orders/{ctx['order_id']}/ack"))


async def run_journey(journey_id: str, client: httpx.AsyncClient) -> RunResult:
    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    ctx: dict[str, Any] = {}
    results: list[StepResult] = []
    failed: str | None = None
    for step in JOURNEYS[journey_id]["steps"]:  # type: ignore[union-attr]
        label = STEP_LABELS[step]
        if failed:
            results.append(StepResult(step, label, "skipped"))
            continue
        s0 = time.monotonic()
        try:
            await _do_step(step, client, ctx)
            results.append(StepResult(step, label, "ok", int((time.monotonic() - s0) * 1000)))
        except StepError as e:
            failed = step
            results.append(StepResult(step, label, "failed", int((time.monotonic() - s0) * 1000), e.kind, e.detail))
        except httpx.TimeoutException:
            failed = step
            results.append(StepResult(step, label, "failed", int((time.monotonic() - s0) * 1000), "timeout", "client timeout"))
        except Exception as e:  # noqa: BLE001 - a probe must never crash the runner
            failed = step
            results.append(StepResult(step, label, "failed", int((time.monotonic() - s0) * 1000), "exception", str(e)[:200]))
    return RunResult(journey_id, started, failed is None, int((time.monotonic() - t0) * 1000), failed, results)


def record_run(result: RunResult) -> None:
    """Persist the run, let the detector look at it, and tell the console."""
    with get_sessionmaker()() as session:
        row = JourneyRun(
            journey=result.journey,
            started_at=result.started_at,
            ok=result.ok,
            total_ms=result.total_ms,
            failed_step=result.failed_step,
            steps=[asdict(s) for s in result.steps],
        )
        session.add(row)
        session.commit()
        opened = evaluate(session, result.journey, row)
    bus.publish("journey.updated", {"journey": result.journey, "ok": result.ok, "total_ms": result.total_ms})
    for incident in opened:
        announce_opened(incident)


def make_client(app: FastAPI | None) -> httpx.AsyncClient:
    cfg = get_settings()
    timeout = cfg.journey_step_timeout_ms / 1000
    if cfg.journey_base_url:
        return httpx.AsyncClient(base_url=cfg.journey_base_url, timeout=timeout)
    assert app is not None, "in-process probing needs the app"
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://shop", timeout=timeout)


class JourneyRunner:
    """One task per journey so a slow journey never overlaps itself."""

    def __init__(self) -> None:
        self._tasks: list[asyncio.Task[None]] = []
        self._client: httpx.AsyncClient | None = None
        self.app: FastAPI | None = None  # set at startup so the verifier can run journeys

    async def run_once(self, journey_id: str, app: FastAPI | None = None) -> RunResult:
        client = self._client or make_client(app or self.app)
        try:
            result = await run_journey(journey_id, client)
        finally:
            if client is not self._client:
                await client.aclose()
        record_run(result)
        return result

    def start(self, app: FastAPI) -> None:
        self.app = app
        if self._tasks:
            return
        self._client = make_client(app)
        for journey_id in JOURNEYS:
            self._tasks.append(asyncio.create_task(self._loop(journey_id), name=f"journey-{journey_id}"))

    async def _loop(self, journey_id: str) -> None:
        interval = get_settings().journey_interval_s
        while True:
            try:
                assert self._client is not None
                record_run(await run_journey(journey_id, self._client))
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("journey loop error: %s", journey_id)
            await asyncio.sleep(interval)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        if self._client:
            await self._client.aclose()
            self._client = None


runner = JourneyRunner()
