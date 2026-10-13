"""Policy engine: decides how a proposed catalog action is allowed to run.
Agents propose; this decides (hard rule 2). High risk always needs a human (hard rule 6)."""
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.ops import AppSetting
from app.policy.catalog import load_catalog

MODES = ("auto", "approval", "blocked")
PACES = {"fast": 0.0, "normal": 0.5, "slow": 2.0}  # seconds of presentational dwell between stages
AGENT_MODES = ("loopwatch", "alert_only", "blind_remediation")
KEY = "policy"


@dataclass
class PolicySettings:
    paused: bool = False
    budget: int = 3
    pace: str = "normal"
    agent_mode: str = "loopwatch"
    modes: dict[str, str] = field(default_factory=dict)  # per-action mode overrides

    def dwell_s(self) -> float:
        return PACES[self.pace]


def load_settings(session: Session) -> PolicySettings:
    row = session.get(AppSetting, KEY)
    raw: dict[str, Any] = row.value if row else {}
    s = PolicySettings()
    for k in ("paused", "budget", "pace", "agent_mode", "modes"):
        if k in raw:
            setattr(s, k, raw[k])
    return s


def save_settings(session: Session, s: PolicySettings) -> None:
    value = {"paused": s.paused, "budget": s.budget, "pace": s.pace, "agent_mode": s.agent_mode, "modes": s.modes}
    row = session.get(AppSetting, KEY)
    if row is None:
        session.add(AppSetting(key=KEY, value=value))
    else:
        row.value = value
    session.commit()


class PolicyError(ValueError):
    pass


def update_settings(session: Session, patch: dict[str, Any]) -> PolicySettings:
    s = load_settings(session)
    catalog = load_catalog()
    if "paused" in patch:
        s.paused = bool(patch["paused"])
    if "budget" in patch:
        if not isinstance(patch["budget"], int) or not 1 <= patch["budget"] <= 10:
            raise PolicyError("budget must be an integer from 1 to 10")
        s.budget = patch["budget"]
    if "pace" in patch:
        if patch["pace"] not in PACES:
            raise PolicyError(f"pace must be one of {list(PACES)}")
        s.pace = patch["pace"]
    if "agent_mode" in patch:
        if patch["agent_mode"] not in AGENT_MODES:
            raise PolicyError(f"agent_mode must be one of {list(AGENT_MODES)}")
        s.agent_mode = patch["agent_mode"]
    for name, mode in (patch.get("modes") or {}).items():
        if name not in catalog:
            raise PolicyError(f"unknown action: {name}")
        if mode not in MODES:
            raise PolicyError(f"mode must be one of {list(MODES)}")
        if mode == "auto" and catalog[name].risk == "high":
            raise PolicyError(f"{name} is high risk and cannot be automatic")
        s.modes[name] = mode
    save_settings(session, s)
    return s


@dataclass
class Decision:
    mode: str  # auto | approval | blocked
    reason: str


def decide(settings: PolicySettings, action_type: str) -> Decision:
    spec = load_catalog()[action_type]
    mode = settings.modes.get(action_type, spec.mode)
    if mode == "blocked":
        return Decision("blocked", "blocked by policy")
    if settings.paused:
        return Decision("approval", "pause switch is on: every action waits for a person")
    if spec.risk == "high":
        return Decision("approval", "high-risk action needs human approval")
    if mode == "approval":
        return Decision("approval", "policy requires approval for this action")
    return Decision("auto", f"{spec.risk} risk, automatic")
