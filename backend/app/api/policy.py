from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import get_session
from app.policy.catalog import load_catalog
from app.policy.engine import PACES, PolicyError, load_settings, update_settings

router = APIRouter(prefix="/policy", tags=["policy"])
Db = Annotated[Session, Depends(get_session)]


def view(session: Session) -> dict[str, Any]:
    s = load_settings(session)
    return {
        "paused": s.paused,
        "budget": s.budget,
        "pace": s.pace,
        "pace_options": list(PACES),
        "agent_mode": s.agent_mode,
        "actions": [
            {
                "name": a.name,
                "risk": a.risk,
                "default_mode": a.mode,
                "mode": s.modes.get(a.name, a.mode),
                "targets": list(a.targets),
                "rollback": a.rollback,
            }
            for a in load_catalog().values()
        ],
    }


@router.get("")
def get_policy(session: Db) -> dict[str, Any]:
    return view(session)


@router.put("")
def put_policy(patch: dict[str, Any], session: Db) -> dict[str, Any]:
    try:
        update_settings(session, patch)
    except PolicyError as e:
        raise HTTPException(422, str(e)) from e
    audit.record(session, "human", "policy_updated", {k: v for k, v in patch.items()})
    return view(session)
