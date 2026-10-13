"""What an investigation may output. Everything is closed-set: causes from a fixed list,
actions from the catalog, evidence ids that exist. There is no free-text command field."""
from pydantic import BaseModel, ConfigDict, Field

from app.agents.causes import CAUSE_ACTIONS, CAUSE_KEYS, Cause
from app.policy.catalog import load_catalog


class ProposalError(ValueError):
    pass


class HypothesisIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cause_key: Cause
    confidence: float = Field(ge=0, le=1)
    supporting: list[str] = Field(default_factory=list, max_length=12)
    weakening: list[str] = Field(default_factory=list, max_length=12)


class ActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    target: str


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypotheses: list[HypothesisIn] = Field(min_length=1, max_length=5)
    actions: list[ActionIn] = Field(min_length=1, max_length=3)


def validate_proposal(p: Proposal, known_refs: set[str]) -> Proposal:
    """Reject anything outside the closed sets. Raises ProposalError."""
    catalog = load_catalog()
    causes = [h.cause_key for h in p.hypotheses]
    if len(set(causes)) != len(causes):
        raise ProposalError("duplicate cause")
    for h in p.hypotheses:
        for ref in h.supporting + h.weakening:
            if ref not in known_refs:
                raise ProposalError(f"unknown evidence id: {ref}")
    top = max(p.hypotheses, key=lambda h: h.confidence).cause_key
    for a in p.actions:
        spec = catalog.get(a.type)
        if spec is None:
            raise ProposalError(f"action not in catalog: {a.type}")
        if a.target not in spec.targets:
            raise ProposalError(f"target {a.target!r} not allowed for {a.type}")
        if a.type not in CAUSE_ACTIONS[top]:
            raise ProposalError(f"{a.type} is not consistent with top cause {top}")
    return p


def json_schema() -> dict:
    """Hand-written JSON schema for structured outputs (closed enums, no free text)."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["hypotheses", "actions"],
        "properties": {
            "hypotheses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["cause_key", "confidence", "supporting", "weakening"],
                    "properties": {
                        "cause_key": {"type": "string", "enum": list(CAUSE_KEYS)},
                        "confidence": {"type": "number"},
                        "supporting": {"type": "array", "items": {"type": "string"}},
                        "weakening": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["type", "target"],
                    "properties": {
                        "type": {"type": "string", "enum": list(load_catalog())},
                        "target": {"type": "string", "enum": sorted({t for a in load_catalog().values() for t in a.targets})},
                    },
                },
            },
        },
    }
