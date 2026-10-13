from fastapi import APIRouter

from app.core.config import get_settings
from app.edge.store import store
from app.schemas.edge import NodeStatus, TelemetryAck, TelemetryMessage

router = APIRouter(prefix="/edge", tags=["edge"])


@router.get("/status", response_model=NodeStatus)
def edge_status(node: str | None = None) -> NodeStatus:
    return store.status(node or get_settings().edge_node)


@router.post("/telemetry", response_model=TelemetryAck)
def post_telemetry(msg: TelemetryMessage) -> TelemetryAck:
    """Same endpoint for a real board and for any other sender. Pending commands ride the reply."""
    return TelemetryAck(accepted=True, commands=store.ingest(msg))
