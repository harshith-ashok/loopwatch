# Evaluation results

Recorded 2026-10-13T10:16:37.087949+00:00. Seed 26.
3 runs per scenario per mode, 2 control runs, 1 decoy runs.

**Model:** off (rule-based playbook).

**Timing:** Accelerated timings (ticks, holds and gateway delays shortened); latencies are not comparable to the real-time demo.

| Metric | Loopwatch | Alert only | Blind restart |
| --- | --- | --- | --- |
| Detection latency (s) | 2.98 (n=12) | 2.71 (n=12) | 2.6 (n=12) |
| Root-cause accuracy | 1.0 (n=12) | n/a (n=0) | n/a (n=0) |
| Recovery success | 0.75 (n=12) | 0.0 (n=12) | 0.583 (n=12) |
| False-positive rate | 0.0 (n=3) | 0.0 (n=3) | 0.0 (n=3) |
| Mean time to resolve (s) | 0.43 (n=9) | n/a (n=0) | 0.95 (n=7) |
| Unsafe action rate | 0.0 (n=15) | n/a (n=0) | 0.75 (n=12) |
| Root fault cleared at close | 0.25 (n=12) | n/a (n=0) | 0.25 (n=12) |

Ratios are 0 to 1 (0.9 = 90%).

## Sample size

This is a **small** sample (3 runs per scenario per mode, 2 control, 1 decoy; 39 runs). A larger
run (10 per scenario) was done earlier on a previous version of the code and was not kept, so it is
not claimed here. Phase 8's target of at least 10 runs per scenario, 5 control and 3 decoy is
**not met by the recorded results**; reproduce it with
`python -m app.harness.run --runs 10 --control 5 --decoy 3` (about 12 minutes, accelerated timings).
With n this small a single run moves a ratio by 8 to 33 points; read them as "behaves as designed",
not as estimates.

## Reading the baselines

- **Blind restart "recovers" 3 of 3 `overheat` runs (ended `resolved`, journeys passing) while the
  fault is still active.** With no diagnosis, the verifier only has the journey to go on and the
  journey passes through a hot node. The recovery column counts that as a success; the
  "root fault cleared" row shows it is not. Loopwatch avoids this because a known cooling fault adds
  a node-temperature check to verification.
- Loopwatch's own "root fault cleared" is 0.25 because `timeout` and `link` are routed around
  (fallback gateway, manual acknowledgement queue), not repaired, and `overheat` is escalated.

## Model-on sample (not part of the table above)

`docs/model-on/` holds a separate run with the diagnosis step done by `gpt-oss:120b-cloud` through
Ollama at temperature 0: 2 runs per scenario, 8 runs, Loopwatch mode only, same accelerated timings.

| Scenario | Ended | Diagnosed by | Top cause |
| --- | --- | --- | --- |
| stall x2 | resolved, resolved | model, model | worker_stalled |
| timeout x2 | resolved, resolved | model, model | gateway_degraded |
| overheat x2 | escalated, escalated | model, playbook | cooling_fault |
| link x2 | mitigated, mitigated | model, model | link_lost |

7 of 8 were diagnosed by the model; one overheat run returned malformed JSON and the rule-based
playbook took over (the intended fallback). All 8 reached the expected end state.

Honest context: an earlier model-on run on slightly earlier code went wrong twice. One `overheat`
was diagnosed as a gateway fault from payment failures left over from the previous scenario, and one
`link` as a cooling fault from the previous scenario's hot telemetry, which led to a proposed
power-cycle (still gated by approval, verified, rolled back and escalated). Both were evidence-scoping
defects, fixed by scoping payment evidence to "since the previous incident closed" and clearing the
node's history on reset. The model path is therefore sensitive to stale evidence; the playbook was
not, because it reads only current state.

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
- Services (database, console) were running on the same machine during the earlier measurement attempts; the recorded run was done with only the harness active.
- The playbook was written alongside these same scenarios, so this shows it works on them, not that it generalises.
- The harness plays the human operator and approves the one high-risk action it is asked about.
- Alert-only has no automated response by design, so its recovery is 0 here; it says nothing about how fast a person would respond.
- Blind restart is a strawman: restart the order worker on any alert, then verify with the same journey check.

Per-run rows are in `results.csv`.
