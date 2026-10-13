"""Rule-based fallback playbook. Maps symptoms found in tool evidence to a cause and a
catalog action with no model involved. Works with the LLM off or failing."""
from dataclasses import dataclass, field
from typing import Any

from app.agents.proposal import ActionIn, HypothesisIn, Proposal
from app.core.config import get_settings

NODE_TARGET = "fulfillment-hub-01"
AMBIGUITY_MARGIN = 0.15  # top two raw scores closer than this means "ask a human"


@dataclass
class Evidence:
    ref: str
    tool: str
    result: dict[str, Any]


@dataclass
class _Score:
    score: float = 0.03
    supporting: list[str] = field(default_factory=list)
    weakening: list[str] = field(default_factory=list)


def _first(evidence: list[Evidence], tool: str) -> Evidence | None:
    return next((e for e in evidence if e.tool == tool and "error" not in e.result), None)


def diagnose(evidence: list[Evidence]) -> Proposal:
    cfg = get_settings()
    scores = {k: _Score() for k in ("worker_stalled", "gateway_degraded", "cooling_fault", "link_lost")}

    q = _first(evidence, "metrics.queue_depth")
    if q:
        r = q.result
        stuck = (r.get("queue_depth") or 0) > 0 or (r.get("paid_unconfirmed_orders") or 0) > 0
        if r.get("consumers") == 0 and stuck:
            scores["worker_stalled"] = _Score(0.9, [q.ref])
        elif r.get("consumers") == 0:
            scores["worker_stalled"] = _Score(0.5, [q.ref])
        else:
            scores["worker_stalled"].weakening.append(q.ref)

    pay = _first(evidence, "db.payments")
    if pay:
        gws = pay.result.get("gateways", {})
        primary = gws.get("primary", {})
        if primary.get("count"):
            slow = (primary.get("mean_latency_ms") or 0) >= cfg.agents_slow_gateway_ms
            if primary.get("failed", 0) > 0 and slow:
                scores["gateway_degraded"] = _Score(0.9, [pay.ref])
            elif primary.get("failed", 0) > 0 or slow:
                scores["gateway_degraded"] = _Score(0.7, [pay.ref])
            else:
                scores["gateway_degraded"].weakening.append(pay.ref)

    health = _first(evidence, "device.health")
    ping = _first(evidence, "network.ping")
    if health:
        h = health.result
        if h.get("seen") and not h.get("online"):
            sup = [health.ref] + ([ping.ref] if ping and not ping.result.get("reachable") else [])
            scores["link_lost"] = _Score(0.9, sup)
        elif h.get("online") and (h.get("temp_c") or 0) > (h.get("temp_limit_c") or 70):
            fan_dead = (h.get("fan_rpm") or 0) < 500
            scores["cooling_fault"] = _Score(0.9 if fan_dead else 0.6, [health.ref])
        else:
            scores["cooling_fault"].weakening.append(health.ref)
            scores["link_lost"].weakening.append(health.ref)

    best = max(scores, key=lambda k: scores[k].score)
    if scores[best].score < 0.4:
        return Proposal(
            hypotheses=[HypothesisIn(cause_key="unknown", confidence=0.5)],
            actions=[ActionIn(type="open_ticket", target="ops-queue")],
        )

    ranked_scores = sorted((s.score for s in scores.values()), reverse=True)
    ambiguous = len(ranked_scores) > 1 and ranked_scores[0] - ranked_scores[1] < AMBIGUITY_MARGIN

    # A matching past incident is listed as supporting context. It does not change confidence.
    mem = _first(evidence, "memory.similar")
    if mem and any(m.get("cause_key") == best for m in mem.result.get("matches", [])[:2]):
        scores[best].supporting.append(mem.ref)

    total = sum(s.score for s in scores.values())
    ranked = sorted(scores.items(), key=lambda kv: kv[1].score, reverse=True)
    hyps = [
        HypothesisIn(
            cause_key=k,  # type: ignore[arg-type]
            confidence=round(s.score / total, 2),
            supporting=s.supporting,
            weakening=s.weakening,
        )
        for k, s in ranked[:3]
    ]
    if ambiguous:
        # Two causes look about equally likely: do not pick an automatic action on a coin flip.
        return Proposal(hypotheses=hyps, actions=[ActionIn(type="open_ticket", target="ops-queue")])
    actions = {
        "worker_stalled": [ActionIn(type="restart_service", target="order-worker")],
        "gateway_degraded": [ActionIn(type="switch_endpoint", target="payments-gateway")],
        "cooling_fault": [ActionIn(type="power_cycle_device", target=NODE_TARGET)],
        "link_lost": [
            ActionIn(type="switch_endpoint", target="hub-ack"),
            ActionIn(type="open_ticket", target="ops-queue"),
        ],
    }[best]
    return Proposal(hypotheses=hyps, actions=actions)
