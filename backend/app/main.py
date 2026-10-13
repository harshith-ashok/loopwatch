import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import audit, edge, events, faults, health, incidents, journeys, overview, policy, score, demo
from app.core.config import get_settings
from app.edge.watcher import edge_runner
from app.journeys.runner import runner
from app.core.db import db_ok, get_sessionmaker
from app.core.logging import configure_logging
from app.shop import routes as shop_routes
from app.agents.seed import seed_past_incidents
from app.shop.seed import seed
from app.shop.worker import worker

log = logging.getLogger("loopwatch")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if db_ok():
        with get_sessionmaker()() as session:
            seed(session)
            seed_past_incidents(session)
            if settings.demo_data:
                from app.demo.seed import seed_demo

                seed_demo(session)
    else:
        log.warning("database unreachable at startup; shop will fail until it is up")
    worker.start()
    if db_ok():
        worker.requeue_unconfirmed()
    runner.app = app
    if settings.demo_seed is not None:
        import random

        from app.edge.simulator import sim
        from app.shop import routes as _routes

        _routes._rng = random.Random(settings.demo_seed)
        sim._rng = random.Random(settings.demo_seed)
    if settings.journey_runner_enabled and db_ok():
        runner.start(app)
    if settings.edge_watch_enabled and db_ok():
        edge_runner.start()
    yield
    await edge_runner.stop()
    await runner.stop()
    await worker.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="Loopwatch", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Never leak a stack trace to the console; it is in the logs.
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse({"detail": "Something went wrong on our side. Check the backend logs."}, status_code=500)

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(events.router, prefix="/api/v1")
    for r in (faults, journeys, incidents, overview, audit, edge, policy, score, demo):
        app.include_router(r.router, prefix="/api/v1")
    app.include_router(shop_routes.router)
    return app


app = create_app()
