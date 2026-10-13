"""Deterministic detection rules. Pure functions, no I/O, no LLM (hard rule 1)."""
import math
import statistics
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Signal:
    rule: str  # step_failure | latency_degradation | state_check
    key: str  # debounce key: one fault should map to one key
    summary: str
    details: dict[str, Any] = field(default_factory=dict)


# A failing step maps to the domain that owns it, so one fault gives one debounce key.
DOMAIN_KEYS = {"ack": "device"}


def domain_key(step: str) -> str:
    return DOMAIN_KEYS.get(step, step)


def step_failure(failed_step: str | None, steps: list[dict[str, Any]]) -> Signal | None:
    """A customer-visible step failed."""
    if failed_step is None:
        return None
    step = next(s for s in steps if s["id"] == failed_step)
    return Signal(
        rule="step_failure",
        key=domain_key(failed_step),
        summary=f"'{step['label']}' failed: {step.get('detail') or step.get('error_kind')}",
        details={"step": failed_step, "error_kind": step.get("error_kind"), "ms": step.get("ms")},
    )


def p95(values: list[int]) -> float:
    ordered = sorted(values)
    return float(ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)])


def latency_degradation(
    window: list[dict[str, Any]],
    baseline_ms: list[int],
    *,
    min_runs: int,
    timeout_rate: float,
    sigma: float,
) -> Signal | None:
    """p95 above baseline mean + sigma*stdev AND timeout rate above threshold, over the window."""
    if len(window) < min_runs or len(baseline_ms) < min_runs:
        return None
    mean = statistics.fmean(baseline_ms)
    std = max(statistics.pstdev(baseline_ms), 0.1 * mean, 5.0)  # floor: a flat baseline is not infinitely tight
    window_p95 = p95([r["total_ms"] for r in window])
    timeouts = sum(
        1 for r in window if any(s.get("error_kind") == "timeout" for s in r["steps"])
    )
    rate = timeouts / len(window)
    if window_p95 <= mean + sigma * std or rate <= timeout_rate:
        return None

    # The slowest step on average names the likely domain, which is the debounce key.
    totals: dict[str, list[int]] = {}
    for r in window:
        for s in r["steps"]:
            if s["status"] != "skipped":
                totals.setdefault(s["id"], []).append(s["ms"])
    slowest = max(totals, key=lambda k: statistics.fmean(totals[k]))
    return Signal(
        rule="latency_degradation",
        key=domain_key(slowest),
        summary=f"p95 {window_p95:.0f} ms vs baseline {mean:.0f} ms, timeout rate {rate:.0%}",
        details={
            "p95_ms": window_p95,
            "baseline_mean_ms": round(mean, 1),
            "baseline_std_ms": round(std, 1),
            "timeout_rate": round(rate, 3),
            "runs": len(window),
            "slowest_step": slowest,
        },
    )


def state_check(stuck_order_ids: list[int], threshold_s: int) -> Signal | None:
    """Payment captured but order still pending beyond the threshold."""
    if not stuck_order_ids:
        return None
    return Signal(
        rule="state_check",
        key="confirm",  # same domain as the 'Order confirmed' step so the two signals merge
        summary=f"{len(stuck_order_ids)} order(s) paid but not confirmed for over {threshold_s} s",
        details={"order_ids": stuck_order_ids[:10], "count": len(stuck_order_ids), "threshold_s": threshold_s},
    )


def overheat(samples: list[tuple[float, float]], limit_c: float, hold_s: float) -> Signal | None:
    """Temperature above the limit continuously for hold_s. samples: (time_s, temp_c), oldest first."""
    if not samples:
        return None
    run_start = None
    for t, temp in reversed(samples):
        if temp <= limit_c:
            break
        run_start = t
    if run_start is None or samples[-1][0] - run_start < hold_s:
        return None
    latest = samples[-1][1]
    return Signal(
        rule="temperature_limit",
        key="device",
        summary=f"temperature {latest:.1f} C above {limit_c:.0f} C for {samples[-1][0] - run_start:.0f} s",
        details={"temp_c": latest, "limit_c": limit_c, "held_s": round(samples[-1][0] - run_start, 1)},
    )


def heartbeat_missed(age_s: float | None, interval_s: float, misses: int) -> Signal | None:
    """No telemetry for `misses` intervals. age_s is None if the node has never reported."""
    if age_s is None or age_s <= interval_s * misses:
        return None
    return Signal(
        rule="heartbeat_missed",
        key="device",
        summary=f"no heartbeat for {age_s:.0f} s ({misses} missed)",
        details={"age_s": round(age_s, 1), "interval_s": interval_s, "misses": misses},
    )
