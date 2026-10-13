# Architecture

```
ESP32 (simulated) ──┐
Journey runner ─────┴─> Detector ─> Coordinator + 4 specialists ─> Policy engine
                                                                    ├─ auto ───────────┐
                                                                    └─ approval (human)┴─> Executor ─> Verifier
                                                                                                         │ 3 passes: resolved / mitigated
                                                                                                         │ fail: rollback + escalate
Across all layers: incident store (PostgreSQL + pgvector), audit log, console over SSE
```

## Stages

| Stage | Code | Notes |
| --- | --- | --- |
| Detect | `app/detector/` | Rules and thresholds only: step failure, p95 over 3 sigma with timeout rate, paid-but-unconfirmed orders, temperature limit, missed heartbeats. No model. Debounced per failing step, so one fault is one incident. |
| Investigate | `app/agents/` | Four specialists run fixed, read-only tool plans and store each result as evidence (E1, E2, ...). A model, if on, ranks causes and proposes actions as closed-set JSON; the rule-based playbook is the fallback. |
| Decide | `app/policy/` | `catalog.yaml` plus persisted settings (pause switch, action budget, per-action mode). High risk always needs approval. |
| Act | `app/executor/` | Five catalog actions only, each capturing state so it can be rolled back. |
| Verify | `app/verifier/` | Re-runs the failed journey 3 times; a cause-specific check can also fail it. The state machine itself refuses to close an incident without 3 passing verifications. |

## Incident states

`investigating -> deciding -> awaiting_approval -> acting -> verifying -> resolved | mitigated | escalated | false_positive | cancelled`

`mitigated`: the journey works through a fallback and the root fault remains (for example the device is still offline).

## Data model

`incident`, `evidence`, `hypothesis`, `action`, `verification`, `audit_event`, `fault_run`, plus
`journey_run`, `ticket`, `past_incident` (pgvector), `app_setting`, and the demo shop tables.

## Live updates

`GET /api/v1/events` (SSE): `journey.updated`, `incident.opened`, `incident.updated`,
`approval.requested`, `edge.telemetry`, `audit.appended`. The frontend turns these into TanStack
Query invalidations.

## What is simulated

The shop, its faults, and the edge node. Fault injection writes a `fault_run` with the true cause;
nothing in the detector or agents reads it. Only the scorecard does.
