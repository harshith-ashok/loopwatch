"""Verifier: the journey must pass 3 times in a row before an incident closes (hard rule 5)."""
import asyncio
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core import audit
from app.core.config import get_settings
from app.edge.store import store
from app.journeys.definitions import JOURNEYS
from app.journeys.runner import runner
from app.models.incidents import Verification

REQUIRED_PASSES = 3


def journey_for(incident_journey: str) -> str:
    """Device incidents are verified through the order journey, which ends at the hub."""
    return incident_journey if incident_journey in JOURNEYS else "order"


def symptom_cleared(cause_key: str | None) -> bool:
    """Cause-specific check on top of the journey. A passing journey is not enough for a
    cooling fault: the node itself has to be back under its temperature limit."""
    cfg = get_settings()
    if cause_key == "cooling_fault":
        st = store.status(cfg.edge_node)
        return bool(st.online and st.temp_c is not None and st.temp_c <= cfg.edge_temp_limit_c)
    return True


def root_fault_remains(cause_key: str | None) -> bool:
    """True when the journey works only through a fallback and the root fault is still there."""
    st = store.status(get_settings().edge_node)
    if cause_key == "link_lost":
        return not st.online
    if cause_key == "cooling_fault":
        return bool(st.temp_c is not None and st.temp_c > get_settings().edge_temp_limit_c)
    return False


@dataclass
class VerifyResult:
    passed: bool
    runs: int
    cleared_root: bool  # False -> mitigated


async def verify(session: Session, incident_id: int, journey: str, cause_key: str | None) -> VerifyResult:
    jid = journey_for(journey)
    passes = 0
    for n in range(1, REQUIRED_PASSES + 1):
        t0 = time.monotonic()
        result = await runner.run_once(jid, runner.app)
        ok = result.ok and symptom_cleared(cause_key)
        ms = int((time.monotonic() - t0) * 1000)
        session.add(Verification(incident_id=incident_id, run_number=n, passed=ok, ms=ms))
        session.commit()
        audit.record(session, "verifier", "verification_run",
                     {"run": n, "passed": ok, "journey": jid, "failed_step": result.failed_step}, incident_id)
        if not ok:
            return VerifyResult(False, n, False)
        passes += 1
        await asyncio.sleep(0.05)
    return VerifyResult(True, passes, not root_fault_remains(cause_key))
