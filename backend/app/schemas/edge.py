from typing import Any

from pydantic import BaseModel, Field


class TelemetryMessage(BaseModel):
    """The one telemetry schema. The simulator, the firmware and POST /edge/telemetry share it."""

    node: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    uptime_s: int = Field(ge=0)
    temp_c: float = Field(ge=-40, le=150)
    rssi_dbm: int = Field(ge=-120, le=0)
    fan_rpm: int = Field(ge=0, le=20000)
    fault: str | None = Field(default=None, max_length=64)


class Sample(BaseModel):
    ago_s: float
    temp_c: float
    rssi_dbm: int
    fan_rpm: int


class NodeStatus(BaseModel):
    node: str
    seen: bool
    online: bool
    last_seen: str | None
    heartbeat_age_s: float | None
    uptime_s: int | None
    temp_c: float | None
    rssi_dbm: int | None
    fan_rpm: int | None
    temp_limit_c: float
    latest: dict[str, Any] | None
    history: list[Sample]


class TelemetryAck(BaseModel):
    accepted: bool
    commands: list[str]
