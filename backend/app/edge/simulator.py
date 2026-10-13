"""Simulated ESP32 fulfillment hub. Emits the same TelemetryMessage a real board would.

Modes:
  normal    healthy readings with a little noise
  overheat  cooling fault: fan spins down to 0 RPM and temperature climbs
  dropping  Wi-Fi degrading: RSSI falls each tick, then the node goes offline
  offline   no messages at all
"""
import random

from app.core.config import get_settings
from app.schemas.edge import TelemetryMessage

MODES = ("normal", "overheat", "dropping", "offline")
BOOT_TICKS = 2  # messages skipped while rebooting after a power cycle


class EdgeSimulator:
    def __init__(self, node: str | None = None, seed: int | None = None) -> None:
        self.node = node or get_settings().edge_node
        self._rng = random.Random(seed)
        self.mode = "normal"
        self.uptime_s = 518_400
        self.temp_c = 41.2
        self.fan_rpm = 4200
        self.rssi_dbm = -58
        self._boot_ticks = 0
        self._drop_ticks = 0
        self.power_cycles = 0

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"unknown simulator mode: {mode}")
        self.mode = mode
        self._drop_ticks = 0

    def restore(self) -> None:
        """Back to healthy. Temperature cools gradually on the next ticks, as it would for real."""
        self.mode = "normal"
        self._drop_ticks = 0
        self._boot_ticks = 0

    def hard_reset(self) -> None:
        """Known healthy state at once (used by the harness reset), not a gradual cool-down."""
        self.mode = "normal"
        self.temp_c, self.fan_rpm, self.rssi_dbm = 41.2, 4200, -58
        self._boot_ticks = self._drop_ticks = 0

    def power_cycle(self) -> None:
        """Reboot: uptime resets and the node is silent for a moment. A broken fan or a lost
        link is not repaired by a reboot, so the mode is left as it is."""
        self.uptime_s = 0
        self._boot_ticks = BOOT_TICKS
        self.power_cycles += 1

    def handle_commands(self, commands: list[str]) -> None:
        if "power_cycle" in commands:
            self.power_cycle()

    def step(self) -> TelemetryMessage | None:
        """Advance one tick. Returns None when the node would send nothing."""
        cfg = get_settings()
        if self._boot_ticks > 0:
            self._boot_ticks -= 1
            return None
        if self.mode == "offline":
            return None
        self.uptime_s += max(1, round(cfg.edge_tick_s))

        n = self._rng.uniform
        if self.mode == "overheat":
            self.fan_rpm = max(0, self.fan_rpm - 1400)
            self.temp_c = min(88.0, self.temp_c + cfg.edge_sim_heat_step_c + n(-0.5, 0.5))
            self.rssi_dbm = round(-58 + n(-2, 2))
        elif self.mode == "dropping":
            self.rssi_dbm = max(-95, self.rssi_dbm - 12)
            self._drop_ticks += 1
            self.fan_rpm = round(4200 + n(-60, 60))
            self.temp_c += (41.2 - self.temp_c) * 0.5 + n(-0.3, 0.3)
            if self._drop_ticks >= cfg.edge_sim_drop_ticks:
                self.mode = "offline"  # the last degraded message is still delivered
        else:  # normal
            self.fan_rpm = min(4200, self.fan_rpm + 1400) if self.fan_rpm < 4000 else round(4200 + n(-60, 60))
            self.temp_c += (41.2 - self.temp_c) * 0.5 + n(-0.3, 0.3)
            self.rssi_dbm = round(-58 + n(-3, 3))

        return TelemetryMessage(
            node=self.node,
            uptime_s=self.uptime_s,
            temp_c=round(self.temp_c, 1),
            rssi_dbm=int(self.rssi_dbm),
            fan_rpm=int(self.fan_rpm),
            fault=None,
        )


sim = EdgeSimulator()
