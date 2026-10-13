"""Recent telemetry per node, node status, and the command queue for devices."""
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.events import bus
from app.schemas.edge import NodeStatus, Sample, TelemetryMessage

KNOWN_COMMANDS = {"power_cycle"}


@dataclass
class Received:
    at: float  # server receive time, seconds since epoch
    msg: TelemetryMessage


class EdgeStore:
    def __init__(self) -> None:
        self._samples: dict[str, deque[Received]] = defaultdict(lambda: deque(maxlen=600))
        self._commands: dict[str, list[str]] = defaultdict(list)

    def reset(self) -> None:
        self._samples.clear()
        self._commands.clear()

    def clear_node(self, node: str) -> None:
        """Forget a node's history (used by the harness reset so old readings are not evidence)."""
        self._samples.pop(node, None)

    def ingest(self, msg: TelemetryMessage, now: float | None = None) -> list[str]:
        """Store a message and return any commands waiting for this node."""
        self._samples[msg.node].append(Received(now if now is not None else time.time(), msg))
        bus.publish(
            "edge.telemetry",
            {"node": msg.node, "temp_c": msg.temp_c, "rssi_dbm": msg.rssi_dbm, "fan_rpm": msg.fan_rpm},
        )
        pending, self._commands[msg.node] = self._commands[msg.node], []
        return pending

    def enqueue_command(self, node: str, command: str) -> None:
        if command not in KNOWN_COMMANDS:
            raise ValueError(f"unknown device command: {command}")
        self._commands[node].append(command)

    def pending_commands(self, node: str) -> list[str]:
        return list(self._commands[node])

    def samples(self, node: str) -> list[Received]:
        return list(self._samples[node])

    def status(self, node: str, now: float | None = None, window_s: float = 60.0) -> NodeStatus:
        cfg = get_settings()
        now = now if now is not None else time.time()
        recent = self.samples(node)
        limit = cfg.edge_temp_limit_c
        if not recent:
            return NodeStatus(
                node=node, seen=False, online=False, last_seen=None, heartbeat_age_s=None,
                uptime_s=None, temp_c=None, rssi_dbm=None, fan_rpm=None, temp_limit_c=limit,
                latest=None, history=[],
            )
        last = recent[-1]
        age = max(0.0, now - last.at)
        online = age <= cfg.edge_tick_s * cfg.edge_missed_beats
        return NodeStatus(
            node=node,
            seen=True,
            online=online,
            last_seen=datetime.fromtimestamp(last.at, tz=timezone.utc).isoformat(),
            heartbeat_age_s=round(age, 1),
            uptime_s=last.msg.uptime_s,
            temp_c=last.msg.temp_c,
            rssi_dbm=last.msg.rssi_dbm,
            fan_rpm=last.msg.fan_rpm,
            temp_limit_c=limit,
            latest=last.msg.model_dump(),
            history=[
                Sample(ago_s=round(now - r.at, 1), temp_c=r.msg.temp_c, rssi_dbm=r.msg.rssi_dbm, fan_rpm=r.msg.fan_rpm)
                for r in recent
                if now - r.at <= window_s
            ],
        )


store = EdgeStore()
