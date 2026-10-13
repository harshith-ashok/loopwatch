"""Runs the specialists, collects evidence, asks the model (if on) for a ranked proposal and
validates it, otherwise uses the playbook. Agents propose; policy decides (Phase 6)."""
import asyncio
import json
import logging
import time
from dataclasses import dataclass

from sqlalchemy import select

from app.agents import llm as llm_mod
from app.agents.causes import CAUSE_LABEL
from app.agents.playbook import Evidence as PBEvidence
from app.agents.playbook import diagnose
from app.agents.proposal import Proposal, ProposalError, json_schema, validate_proposal
from app.agents.specialists import SPECIALISTS
from app.agents.tools import call_tool
from app.core import audit
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.events import bus
from app.core.incident_machine import add_evidence, transition
from app.models.incidents import Action, Hypothesis
from app.models.journeys import Incident
from app.policy.catalog import load_catalog

log = logging.getLogger("agents")


@dataclass
class Result:
    incident_id: int
    source: str  # llm | playbook
    top_cause: str
    confidence: float
    fallback_reason: str | None
    steps: int


async def _propose_with_llm(client: llm_mod.LLMClient, incident: Incident, evidence: list[PBEvidence]) -> Proposal:
    cfg = get_settings()
    payload = [{"id": e.ref, "tool": e.tool, "result": e.result} for e in evidence]
    user = llm_mod.build_user_prompt(f"{incident.title} (detected by {incident.rule})", payload)
    try:
        text = await asyncio.wait_for(
            asyncio.to_thread(client.complete_json, llm_mod.SYSTEM_PROMPT, user, json_schema(), cfg.agents_llm_timeout_s),
            timeout=cfg.agents_llm_timeout_s + 2,
        )
    except asyncio.TimeoutError as e:
        raise llm_mod.LLMUnavailable("model timed out") from e
    try:
        proposal = Proposal.model_validate(json.loads(text))
        return validate_proposal(proposal, {e.ref for e in evidence})
    except (ValueError, ProposalError) as e:  # json errors, schema errors, closed-set violations
        raise llm_mod.LLMUnavailable(f"invalid model output: {str(e)[:200]}") from e


async def investigate(incident_id: int) -> Result | None:
    cfg = get_settings()
    started = time.monotonic()
    with get_sessionmaker()() as session:
        incident = session.get(Incident, incident_id)
        if incident is None or incident.state != "investigating":
            return None
        if session.scalar(select(Hypothesis.id).where(Hypothesis.incident_id == incident_id).limit(1)):
            return None

        audit.record(session, "agent", "investigation_started", {"specialists": [s.name for s in SPECIALISTS]}, incident_id)

        # The detector signal is already E1; include it so the model and playbook can cite it.
        evidence: list[PBEvidence] = []
        from app.models.incidents import Evidence as EvidenceRow

        for row in session.scalars(select(EvidenceRow).where(EvidenceRow.incident_id == incident_id).order_by(EvidenceRow.id)):
            evidence.append(PBEvidence(row.ref, row.tool, row.result))

        steps, limit_hit = 0, None
        for spec in SPECIALISTS:
            for tool, args in spec.plan(incident):
                if steps >= cfg.agents_max_steps:
                    limit_hit = "step_limit"
                    break
                if time.monotonic() - started > cfg.agents_time_limit_s:
                    limit_hit = "time_limit"
                    break
                try:
                    result = call_tool(session, tool, args)
                except Exception as e:  # noqa: BLE001 - a failing tool is evidence, not a crash
                    result = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
                row = add_evidence(session, incident_id, tool, args, result)
                evidence.append(PBEvidence(row.ref, tool, result))
                steps += 1
                bus.publish("incident.updated", {"id": incident_id, "state": incident.state, "evidence": row.ref})
                await asyncio.sleep(0)  # let SSE flush so the console shows evidence arriving
            if limit_hit:
                break

        source, fallback_reason = "playbook", None
        proposal: Proposal | None = None
        try:
            proposal = await _propose_with_llm(llm_mod.get_llm(), incident, evidence)
            source = "llm"
        except llm_mod.LLMUnavailable as e:
            fallback_reason = str(e)
        if proposal is None:
            proposal = diagnose(evidence)

        catalog = load_catalog()
        ordered = sorted(proposal.hypotheses, key=lambda h: h.confidence, reverse=True)
        for rank, h in enumerate(ordered, start=1):
            session.add(
                Hypothesis(
                    incident_id=incident_id, rank=rank, cause=CAUSE_LABEL[h.cause_key], cause_key=h.cause_key,
                    confidence=h.confidence, supporting=h.supporting, weakening=h.weakening,
                )
            )
        for a in proposal.actions:
            spec = catalog[a.type]
            session.add(
                Action(incident_id=incident_id, type=a.type, target=a.target, risk=spec.risk, mode=spec.mode,
                       state="proposed", rollback=spec.rollback)
            )
        session.commit()

        top = ordered[0]
        audit.record(
            session, "agent", "diagnosis_complete",
            {"source": source, "top_cause": top.cause_key, "confidence": top.confidence,
             "actions": [f"{a.type}:{a.target}" for a in proposal.actions],
             "fallback_reason": fallback_reason, "steps": steps, "limit_hit": limit_hit},
            incident_id,
        )
        transition(session, incident, "deciding", "agent", f"diagnosis from {source}")
        return Result(incident_id, source, top.cause_key, top.confidence, fallback_reason, steps)
