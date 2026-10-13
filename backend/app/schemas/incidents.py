"""Response shapes for the incident API. frontend/src/lib/types.ts mirrors these."""
from typing import Any

from pydantic import BaseModel


class PendingAction(BaseModel):
    id: int
    type: str
    target: str
    risk: str
    rollback: str


class IncidentSummary(BaseModel):
    id: int
    title: str
    journey: str
    state: str
    stage: str
    rule: str
    signals: dict[str, Any]
    opened_at: str
    closed_at: str | None
    is_demo: bool
    top_cause: str | None
    pending_action: PendingAction | None


class EvidenceOut(BaseModel):
    ref: str
    tool: str
    args: dict[str, Any]
    result: dict[str, Any]
    created_at: str


class HypothesisOut(BaseModel):
    rank: int
    cause: str
    cause_key: str
    confidence: float
    supporting: list[str]
    weakening: list[str]


class ActionOut(BaseModel):
    id: int
    type: str
    target: str
    risk: str
    mode: str
    state: str
    rollback: str
    created_at: str
    approved_by: str | None


class VerificationOut(BaseModel):
    run_number: int
    passed: bool
    ms: int
    created_at: str


class TimelineEvent(BaseModel):
    id: int
    ts: str
    actor: str
    action: str
    detail: dict[str, Any]


class IncidentDetail(IncidentSummary):
    timeline: list[TimelineEvent]
    evidence: list[EvidenceOut]
    hypotheses: list[HypothesisOut]
    actions: list[ActionOut]
    verifications: list[VerificationOut]
