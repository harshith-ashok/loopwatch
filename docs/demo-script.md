# Demo script (about 3 minutes)

Timing: the defaults are a demo profile. From a click, an incident opens in about 2 s (stall,
timeout), 5 s (link) or 6 s (overheat), and the whole loop closes in roughly 4 to 9 s. The spec
thresholds (10 s overheat hold, 2 s heartbeat) are pinned in the test suite.

Setup: backend and frontend running, `LOOPWATCH_DEMO_DATA=true` so history is not empty, pace
on **Normal**, all journeys green on the Overview.

| Time | Do | Say | Expect |
| --- | --- | --- | --- |
| 0:00 | Overview | "Four customer journeys, checked every 2 seconds, plus an edge node in the fulfilment hub." | 4 of 4 healthy, no open incidents |
| 0:20 | Click **Order worker stalls** | "A worker stops consuming orders. Payments still succeed, so a dashboard looks fine." | Order journey turns Broken in a few seconds |
| 0:40 | Watch the incident card | "Detected by rules, no model. Four specialists collect evidence." | Stage bar moves; evidence appears |
| 1:00 | Open the incident | "It names the cause with evidence ids, proposes a restart, and the policy lets a medium-risk action run." | Top cause "Order worker stalled", `restart_service` |
| 1:20 | Wait | "It will not close until the journey passes three times in a row." | Verification 1, 2, 3, then Resolved |
| 1:40 | Click **Edge node overheats** | "Now the hardware. The fan stalls and the node heats up." | Temperature climbs on the Edge page |
| 2:10 | Approval card appears | "Power cycling a device is high risk, so it asks a person. It shows the rollback plan." | Approval card with rollback |
| 2:20 | **Approve** | | Action runs |
| 2:30 | Wait | "A reboot does not fix a dead fan. Verification fails, so it rolls back and escalates instead of pretending." | Escalated, ticket opened |
| 2:50 | Scorecard | "These numbers come from faults we injected with known causes." | Metrics and baseline table |

Alternates if something misbehaves: **Payment gateway times out** (auto, resolved) and **Edge node
loses Wi-Fi** (auto, mitigated).

If the console looks wrong: **Reset everything** returns the system to a known healthy state in
under a second.

Not yet done: the run has not been recorded on video, and the script has not been rehearsed with
a person. `python -m app.harness.rehearse` runs the same path automatically and prints timings.
