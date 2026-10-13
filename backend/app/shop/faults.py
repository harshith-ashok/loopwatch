"""Fault switches and routing state for the demo shop. In-process, single worker."""
from dataclasses import dataclass


@dataclass
class ShopState:
    stall: bool = False  # order worker stops consuming
    timeout: bool = False  # primary gateway slow and erroring
    timeout_first: bool = False  # the first charge after injection always times out (demo: no waiting on a 22% roll)
    slow: bool = False  # decoy: primary gateway slow but healthy (no errors); should NOT open an incident
    payment_route: str = "primary"  # "primary" | "fallback"; switch_endpoint flips this
    ack_route: str = "hub"  # "hub" | "manual"; acks go to a manual queue when the hub is unusable

    def reset(self) -> None:
        self.stall = False
        self.timeout = False
        self.timeout_first = False
        self.slow = False
        self.payment_route = "primary"
        self.ack_route = "hub"


state = ShopState()
