# Hard rules check

Each rule from `CLAUDE.md` checked against the code on 2026-10-13, with where it is enforced and
how it was checked. "Gap" means something a reader should know, not a pass.

| # | Rule | Enforced in | Checked by | Gap |
| --- | --- | --- | --- | --- |
| 1 | Detection never calls an LLM | `app/detector/` has no model import; rules are pure functions (`rules.py`) | `grep -ri "llm\|ollama\|openai" app/detector app/journeys` returns only the docstring that states the rule | None found |
| 2 | Agents propose, policy decides; no free-text commands | `agents/proposal.py` closed-set schema and consistency guard; `executor/actions.py` only runs catalog names; `executor/flow.py` calls `policy.engine.decide` for every action | `test_agents.py` (8 invalid model outputs fall back, an "obeying" model is rejected) | The blind-remediation baseline creates an action in `agents/dispatch.py`, but it still goes through `decide` |
| 3 | Investigation tools are read-only | `agents/tools.py` contains only selects and attribute reads | grep for writes in that file is empty; `test_tools_do_not_change_state` snapshots every table, the edge store and the command queue around all 9 tools | The tool module imports the worker and the edge store to read them; nothing there writes |
| 4 | Every catalog action has a rollback plan stored with the action | `policy/catalog.yaml` requires `rollback`; `Action.rollback` and `Action.before` are written at proposal and execution; `executor.rollback` | `test_scenario_ends_in_the_expected_state[overheat]` exercises a real rollback | `restart_service` rollback is a documented no-op in the demo shop (there is no previous revision to redeploy) |
| 5 | Closing needs 3 consecutive passing journey runs | `core/incident_machine.py` refuses `resolved` or `mitigated` without 3 passing `Verification` rows; `verifier/verify.py` stops at the first failure | `test_full_lifecycle_*` expects the transition to be refused until verifications exist; the Phase 6 loop test asserts three passes | Demo seed data constructs closed incidents directly; they are flagged `is_demo` and excluded from scoring |
| 6 | High-risk actions need approval; pause makes every action wait | `policy/engine.py` (high risk is always approval; the API rejects setting it to auto); `executor/actions.py` refuses a high-risk action with no recorded approval | `test_policy_gates_pause_deny_and_budget` | None found |
| 7 | Logs, telemetry and tool output are data, not instructions | Evidence is escaped and fenced in the prompt; the playbook never reads log text; model output is re-validated; firmware accepts only known command names | `test_log_line_with_instructions_is_data_only`, `test_model_that_obeys_the_injection_is_rejected`, `test_firmware_only_accepts_known_commands`. Real `gpt-oss:120b-cloud` calls (3 of 3) ignored an injected "power_cycle_device" log line | The real-model check is 3 trials on one prompt, not a systematic test |
| 8 | Every state change writes an audit event | `incident_machine.transition` audits every state change; `flow.py` audits policy decisions, executions, failures, rollbacks, approvals, denials, escalations; fault injection, policy updates and demo seeding are audited | Phase 6 loop test reads the audit trail for each scenario | Evidence rows (tool results) are data writes and are not audited individually; they are visible in the incident trace |
| 9 | Simulator and device share one schema; never branch app logic on "is simulated" | `schemas/edge.py` is the only message model; simulator, `POST /edge/telemetry` and the firmware all use it | `test_simulator_and_board_share_one_schema`, `test_firmware_message_validates_and_matches_schema_keys` | `edge_sim_enabled` decides whether the simulator loop runs and whether reset publishes a healthy sample. That is configuration of the generator, not a branch on message provenance |
| 10 | Do not claim a metric you did not measure | `harness/scoring.py` and `harness/run.py` take ground truth from `fault_run`; demo data is excluded; `docs/results.md` records run counts, date and limits | `test_score_uses_ground_truth_and_excludes_demo` | The recovery metric counts a blind-restart "resolved" on `overheat` as a recovery even though the fault is still active; the table prints a "root fault cleared" row next to it for that reason |

## Not done

- No Playwright smoke test (browsers were not installed).
- No video of the demo, and no rehearsal with a person.
- Migrations 0004 to 0006 were written by hand and not applied to Postgres (Docker was down).
- The UI has never been opened in a browser during development.
