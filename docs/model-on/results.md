# Evaluation results

Recorded 2026-10-13T10:20:13.320707+00:00. Seed 26.
2 runs per scenario per mode, 0 control runs, 0 decoy runs.

**Model:** ollama gpt-oss:120b-cloud (temperature 0); playbook on any model failure.

**Timing:** Accelerated timings (ticks, holds and gateway delays shortened); latencies are not comparable to the real-time demo.

| Metric | Loopwatch |
| --- | --- |
| Detection latency (s) | 3.37 (n=8) |
| Root-cause accuracy | 1.0 (n=8) |
| Recovery success | 0.75 (n=8) |
| False-positive rate | n/a (n=0) |
| Mean time to resolve (s) | 6.45 (n=6) |
| Unsafe action rate | 0.0 (n=8) |
| Root fault cleared at close | 0.25 (n=8) |

Ratios are 0 to 1 (0.9 = 90%).

## Definitions

- **Detection latency**: seconds from injection to incident opening, over injected runs that opened one.
- **Root-cause accuracy**: top hypothesis equals the injected true cause, over incidents that were diagnosed. Alert-only and blind restart never diagnose, so n=0.
- **Recovery success**: incident ended resolved or mitigated AND all four journeys passed in an independent check after close, over all injected runs (a missed detection counts as a failure). `overheat` is designed to end escalated, so Loopwatch is expected to fail it here.
- **False-positive rate**: control runs (no fault) and decoy runs (slow but healthy gateway) that opened any incident. Measured once in Loopwatch mode; the detector is shared by all modes.
- **Mean time to resolve**: seconds from incident opening to resolved or mitigated, over successful recoveries.
- **Unsafe action rate**: executed actions that were high risk without approval, or not consistent with the injected true cause.
- **Root fault cleared at close**: the injected fault was no longer active when the incident closed (ground truth). `timeout` and `link` are routed around, not cleared.

## Honest limits

- One process, one seed, simulated shop and simulated edge node; no physical device was involved.
- The playbook was written alongside these same scenarios, so this shows it works on them, not that it generalises.
- The harness plays the human operator and approves the one high-risk action it is asked about.
- Alert-only has no automated response by design, so its recovery is 0 here; it says nothing about how fast a person would respond.
- Blind restart is a strawman: restart the order worker on any alert, then verify with the same journey check.

Per-run rows are in `results.csv`.
