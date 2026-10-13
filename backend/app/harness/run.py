"""Evaluation harness.

    python -m app.harness.run --runs 10 --control 5 --decoy 3

Injects each scenario N times with randomised timing against the in-process app, in three
modes (Loopwatch, alert-only, blind restart), and writes docs/results.{csv,json,md}.
Ground truth comes from the injected fault, never from anything the detector can see.

Timings are ACCELERATED (shorter ticks, holds and gateway delays) so a full run takes
minutes, not hours. Latencies here are not comparable to the real-time demo.
"""
import argparse
import asyncio
import csv
import json
import os
import random
import statistics
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ACCELERATED = {
    "LOOPWATCH_JOURNEY_INTERVAL_S": "0.5",
    "LOOPWATCH_JOURNEY_ORDER_TIMEOUT_MS": "1200",
    "LOOPWATCH_JOURNEY_STEP_TIMEOUT_MS": "3000",
    "LOOPWATCH_SHOP_PAYMENT_OK_MS": "20",
    "LOOPWATCH_SHOP_PAYMENT_SLOW_MS": "300",
    "LOOPWATCH_SHOP_PAYMENT_TIMEOUT_MS": "600",
    "LOOPWATCH_SHOP_WORKER_TICK_MS": "20",
    "LOOPWATCH_SHOP_ACK_HOT_SLOW_MS": "300",
    "LOOPWATCH_EDGE_TICK_S": "0.5",
    "LOOPWATCH_EDGE_WATCH_S": "0.25",
    "LOOPWATCH_EDGE_OVERHEAT_HOLD_S": "3",
    "LOOPWATCH_EDGE_SIM_HEAT_STEP_C": "12",
    "LOOPWATCH_DETECTOR_WINDOW_S": "10",
    "LOOPWATCH_DETECTOR_STATE_CHECK_S": "4",
    "LOOPWATCH_AGENTS_SLOW_GATEWAY_MS": "100",
}
SCENARIOS = ["stall", "timeout", "overheat", "link"]
TRUE_CAUSE = {"stall": "worker_stalled", "timeout": "gateway_degraded", "overheat": "cooling_fault",
              "link": "link_lost", "decoy": "none"}
TERMINAL = {"resolved", "mitigated", "escalated", "false_positive", "cancelled"}


@dataclass
class RunRecord:
    mode: str
    kind: str  # scenario | control | decoy
    scenario: str
    run: int
    pre_delay_s: float
    incidents: int = 0
    state: str = "none"
    top_cause: str | None = None
    detection_s: float | None = None
    close_s: float | None = None
    actions: str = ""
    unsafe_actions: int = 0
    executed_actions: int = 0
    journeys_ok_at_end: bool | None = None
    fault_active_at_end: bool | None = None
    approvals: int = 0
    diagnosis_source: str = ""  # llm | playbook | (empty: no diagnosis)
    fallback_reason: str = ""


@dataclass
class Aggregate:
    runs: int = 0
    detect: list[float] = field(default_factory=list)


def _ratio(num: int, den: int) -> dict:
    return {"value": round(num / den, 3) if den else None, "n": den}


def _mean(xs: list[float]) -> dict:
    return {"value": round(statistics.fmean(xs), 2) if xs else None, "n": len(xs)}


def aggregate(records: list[RunRecord]) -> dict:
    inj = [r for r in records if r.kind == "scenario"]
    quiet = [r for r in records if r.kind in ("control", "decoy")]
    detected = [r for r in inj if r.incidents > 0]
    diagnosed = [r for r in detected if r.top_cause is not None]
    closed = [r for r in detected if r.state in TERMINAL and r.state != "cancelled"]
    ok = [r for r in closed if r.state in ("resolved", "mitigated") and r.journeys_ok_at_end]
    executed = sum(r.executed_actions for r in records)
    unsafe = sum(r.unsafe_actions for r in records)
    return {
        "detection_latency_s": _mean([r.detection_s for r in detected if r.detection_s is not None]),
        "root_cause_accuracy": _ratio(sum(1 for r in diagnosed if r.top_cause == TRUE_CAUSE[r.scenario]), len(diagnosed)),
        "recovery_success": _ratio(len(ok), len(inj)),
        "false_positive_rate": _ratio(sum(1 for r in quiet if r.incidents > 0), len(quiet)),
        "mttr_s": _mean([r.close_s for r in ok if r.close_s is not None]),
        "unsafe_action_rate": _ratio(unsafe, executed),
        "root_fault_cleared": _ratio(sum(1 for r in closed if r.fault_active_at_end is False), len(closed)),
    }


async def run_all(args: argparse.Namespace) -> dict:
    # Imports happen after the environment is set, because settings are cached at import.
    import httpx
    from sqlalchemy import select

    from app.agents.causes import CAUSE_ACTIONS
    from app.core.db import Base, get_engine, get_sessionmaker
    from app.edge.simulator import sim
    from app.journeys.definitions import JOURNEYS
    from app.journeys.runner import runner
    from app.main import app
    from app.models.incidents import Action, Hypothesis
    from app.models.journeys import Incident
    from app.models.ops import AuditEvent
    from app.shop.faults import state as shop_state

    if get_engine().dialect.name == "sqlite":
        Base.metadata.create_all(get_engine())

    def fault_active(scenario: str) -> bool:
        return {
            "stall": shop_state.stall, "timeout": shop_state.timeout, "decoy": shop_state.slow,
            "overheat": sim.mode == "overheat", "link": sim.mode in ("dropping", "offline"),
        }.get(scenario, False)

    records: list[RunRecord] = []
    rng = random.Random(args.seed)

    async with app.router.lifespan_context(app):
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://lw", timeout=30)

        async def configure(mode: str) -> None:
            r = await client.put("/api/v1/policy", json={"agent_mode": mode, "pace": "fast", "paused": False, "budget": 3})
            r.raise_for_status()

        async def reset() -> int:
            await client.post("/api/v1/faults/reset")
            await asyncio.sleep(1.5)  # let healthy telemetry and journeys re-establish
            with get_sessionmaker()() as s:
                return s.scalar(select(Incident.id).order_by(Incident.id.desc()).limit(1)) or 0

        async def one(mode: str, kind: str, scenario: str, n: int) -> RunRecord:
            base_id = await reset()
            delay = round(rng.uniform(0.0, 1.5), 2)
            rec = RunRecord(mode, kind, scenario, n, delay)
            await asyncio.sleep(delay)
            t_inject = time.monotonic()
            if kind != "control":
                (await client.post(f"/api/v1/faults/{scenario}")).raise_for_status()
            horizon = {"control": 8.0, "decoy": 8.0}.get(kind, 45.0)
            opened_at: float | None = None
            approved = False
            while time.monotonic() - t_inject < horizon:
                await asyncio.sleep(0.1)
                with get_sessionmaker()() as s:
                    inc = s.scalar(select(Incident).where(Incident.id > base_id).order_by(Incident.id).limit(1))
                    if inc is None:
                        continue
                    if opened_at is None:
                        opened_at = time.monotonic()
                        rec.detection_s = round(opened_at - t_inject, 2)
                    st = inc.state
                    pend = s.scalar(select(Action.id).where(Action.incident_id == inc.id, Action.state == "awaiting_approval"))
                if st == "awaiting_approval" and pend and not approved:
                    approved = True
                    rec.approvals += 1
                    await client.post(f"/api/v1/incidents/{inc.id}/approve", json={"operator": "harness-operator"})
                if st in TERMINAL:
                    rec.close_s = round(time.monotonic() - opened_at, 2)
                    break
                if mode == "alert_only" and time.monotonic() - opened_at > 5.0:
                    break  # nothing will happen: baseline has no automated response

            with get_sessionmaker()() as s:
                incs = list(s.scalars(select(Incident).where(Incident.id > base_id).order_by(Incident.id)))
                rec.incidents = len(incs)
                if incs:
                    first = incs[0]
                    rec.state = first.state
                    rec.top_cause = s.scalar(select(Hypothesis.cause_key).where(
                        Hypothesis.incident_id == first.id, Hypothesis.rank == 1))
                    diag = s.scalar(select(AuditEvent).where(AuditEvent.incident_id == first.id,
                                                             AuditEvent.action == "diagnosis_complete"))
                    if diag:
                        rec.diagnosis_source = diag.detail.get("source", "")
                        rec.fallback_reason = str(diag.detail.get("fallback_reason") or "")[:120]
                    acts = list(s.scalars(select(Action).where(Action.incident_id == first.id)))
                    rec.actions = ",".join(f"{a.type}:{a.state}" for a in acts)
                    for a in acts:
                        if a.state in ("done", "rolled_back"):
                            rec.executed_actions += 1
                            consistent = scenario in TRUE_CAUSE and a.type in CAUSE_ACTIONS.get(TRUE_CAUSE[scenario], set())
                            if (a.risk == "high" and not a.approved_by) or (kind == "scenario" and not consistent):
                                rec.unsafe_actions += 1
            rec.fault_active_at_end = fault_active(scenario) if kind != "control" else False
            if kind == "scenario" and rec.incidents:
                results = [await runner.run_once(j, app) for j in JOURNEYS]
                rec.journeys_ok_at_end = all(r.ok for r in results)
            return rec

        plan: list[tuple[str, str, str, int]] = []
        for mode in args.modes:
            for n in range(1, args.runs + 1):
                for sc in SCENARIOS:
                    plan.append((mode, "scenario", sc, n))
        for n in range(1, args.control + 1):
            plan.append(("loopwatch", "control", "none", n))
        for n in range(1, args.decoy + 1):
            plan.append(("loopwatch", "decoy", "decoy", n))

        for i, (mode, kind, sc, n) in enumerate(plan, 1):
            await configure(mode)
            rec = await one(mode, kind, sc, n)
            records.append(rec)
            print(f"[{i}/{len(plan)}] {mode:18} {kind:8} {sc:9} -> {rec.state:11} detect={rec.detection_s} "
                  f"cause={rec.top_cause} actions={rec.actions}", flush=True)
        await configure("loopwatch")
        await client.post("/api/v1/faults/reset")
        await client.aclose()

    per_mode = {m: aggregate([r for r in records if r.mode == m and r.kind == "scenario"]) for m in args.modes}
    # False positives are a property of the shared detector, measured once in Loopwatch mode.
    quiet = aggregate([r for r in records if r.kind in ("control", "decoy")])
    for m in per_mode:
        per_mode[m]["false_positive_rate"] = quiet["false_positive_rate"]
    return {
        "records": records,
        "summary": {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "seed": args.seed,
            "runs_per_scenario": args.runs,
            "control_runs": args.control,
            "decoy_runs": args.decoy,
            "model": args.model_label,
            "timing_note": "Accelerated timings (ticks, holds and gateway delays shortened); "
                           "latencies are not comparable to the real-time demo.",
            "modes": per_mode,
        },
    }


def write_outputs(out: Path, result: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    records: list[RunRecord] = result["records"]
    with (out / "results.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(records[0]).keys()))
        w.writeheader()
        for r in records:
            w.writerow(asdict(r))
    (out / "results.json").write_text(json.dumps(result["summary"], indent=2))

    s = result["summary"]
    names = {"loopwatch": "Loopwatch", "alert_only": "Alert only", "blind_remediation": "Blind restart"}
    labels = {
        "detection_latency_s": "Detection latency (s)", "root_cause_accuracy": "Root-cause accuracy",
        "recovery_success": "Recovery success", "false_positive_rate": "False-positive rate",
        "mttr_s": "Mean time to resolve (s)", "unsafe_action_rate": "Unsafe action rate",
        "root_fault_cleared": "Root fault cleared at close",
    }

    def cell(m: dict) -> str:
        return f"n/a (n={m['n']})" if m["value"] is None else f"{m['value']} (n={m['n']})"

    lines = [
        "# Evaluation results", "",
        f"Recorded {s['recorded_at']}. Seed {s['seed']}.",
        f"{s['runs_per_scenario']} runs per scenario per mode, {s['control_runs']} control runs, {s['decoy_runs']} decoy runs.",
        "", f"**Model:** {s['model']}.", "", f"**Timing:** {s['timing_note']}", "",
        "| Metric | " + " | ".join(names.get(m, m) for m in s["modes"]) + " |",
        "| --- | " + " | ".join("---" for _ in s["modes"]) + " |",
    ]
    for key, label in labels.items():
        lines.append(f"| {label} | " + " | ".join(cell(s["modes"][m][key]) for m in s["modes"]) + " |")
    lines += [
        "", "Ratios are 0 to 1 (0.9 = 90%).", "",
        "## Definitions", "",
        "- **Detection latency**: seconds from injection to incident opening, over injected runs that opened one.",
        "- **Root-cause accuracy**: top hypothesis equals the injected true cause, over incidents that were diagnosed. Alert-only and blind restart never diagnose, so n=0.",
        "- **Recovery success**: incident ended resolved or mitigated AND all four journeys passed in an independent check after close, over all injected runs (a missed detection counts as a failure). `overheat` is designed to end escalated, so Loopwatch is expected to fail it here.",
        "- **False-positive rate**: control runs (no fault) and decoy runs (slow but healthy gateway) that opened any incident. Measured once in Loopwatch mode; the detector is shared by all modes.",
        "- **Mean time to resolve**: seconds from incident opening to resolved or mitigated, over successful recoveries.",
        "- **Unsafe action rate**: executed actions that were high risk without approval, or not consistent with the injected true cause.",
        "- **Root fault cleared at close**: the injected fault was no longer active when the incident closed (ground truth). `timeout` and `link` are routed around, not cleared.",
        "", "## Honest limits", "",
        "- One process, one seed, simulated shop and simulated edge node; no physical device was involved.",
        "- The playbook was written alongside these same scenarios, so this shows it works on them, not that it generalises.",
        "- The harness plays the human operator and approves the one high-risk action it is asked about.",
        "- Alert-only has no automated response by design, so its recovery is 0 here; it says nothing about how fast a person would respond.",
        "- Blind restart is a strawman: restart the order worker on any alert, then verify with the same journey check.",
        "", "Per-run rows are in `results.csv`.", "",
    ]
    (out / "results.md").write_text("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--control", type=int, default=5)
    ap.add_argument("--decoy", type=int, default=3)
    ap.add_argument("--seed", type=int, default=26)
    ap.add_argument("--modes", nargs="+", default=["loopwatch", "alert_only", "blind_remediation"])
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[3] / "docs")
    ap.add_argument("--model-label", default="off (rule-based playbook)",
                    help="text recorded as the model configuration; the true source is in each run row")
    ap.add_argument("--db", default="", help="database URL; default is a temporary SQLite file")
    args = ap.parse_args()

    for k, v in ACCELERATED.items():
        os.environ.setdefault(k, v)
    os.environ.setdefault("LOOPWATCH_AGENTS_ENABLED", "true")
    os.environ.setdefault("LOOPWATCH_LOG_LEVEL", "ERROR")
    os.environ["LOOPWATCH_DATABASE_URL"] = args.db or f"sqlite:///{tempfile.mkdtemp(prefix='lw-eval-')}/eval.db"
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    result = asyncio.run(run_all(args))
    write_outputs(args.out, result)
    print(json.dumps(result["summary"]["modes"], indent=1))


if __name__ == "__main__":
    main()
