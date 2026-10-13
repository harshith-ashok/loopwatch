"""Root causes the system can name, and which catalog actions are consistent with each."""
from typing import Literal

Cause = Literal["worker_stalled", "gateway_degraded", "cooling_fault", "link_lost", "unknown"]

CAUSE_KEYS: tuple[str, ...] = ("worker_stalled", "gateway_degraded", "cooling_fault", "link_lost", "unknown")

CAUSE_LABEL = {
    "worker_stalled": "Order worker stalled",
    "gateway_degraded": "Primary payment gateway degraded",
    "cooling_fault": "Cooling fault on the edge node",
    "link_lost": "Edge node link lost",
    "unknown": "Cause not identified",
}

# An action the model proposes must be consistent with its own top hypothesis. This is a
# guard against a manipulated or confused model naming a valid-but-unrelated action.
CAUSE_ACTIONS: dict[str, set[str]] = {
    "worker_stalled": {"restart_service", "retry_operation", "open_ticket"},
    "gateway_degraded": {"switch_endpoint", "retry_operation", "open_ticket"},
    "cooling_fault": {"power_cycle_device", "open_ticket"},
    "link_lost": {"switch_endpoint", "open_ticket", "retry_operation"},
    "unknown": {"open_ticket"},
}
