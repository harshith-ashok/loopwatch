// Sample data so pages can be built before the agents exist. Only used when
// VITE_USE_FIXTURES=true; never imported in a normal run.
import type { AuditEventView, EdgeStatusView, IncidentDetailView, IncidentView } from "./types";

export const FIXTURE_DETAIL: IncidentDetailView = {
  id: 101,
  title: "Order confirmation: 'Order confirmed' failed: order still 'paid' after 3000 ms",
  journey: "order",
  state: "awaiting_approval",
  stage: "decide",
  failed_stage: null,
  rule: "step_failure",
  signals: { count: 4, rules_seen: ["step_failure", "state_check"] },
  opened_at: "2026-10-13T06:30:00+00:00",
  closed_at: null,
  is_demo: true,
  top_cause: "worker_stalled",
  pending_action: null,
  timeline: [
    { id: 1, ts: "2026-10-13T06:30:00+00:00", actor: "detector", action: "incident_opened", detail: { rule: "step_failure" } },
    { id: 2, ts: "2026-10-13T06:30:04+00:00", actor: "agent", action: "state_changed", detail: { from: "investigating", to: "deciding" } },
    { id: 4, ts: "2026-10-13T06:30:05+00:00", actor: "agent", action: "diagnosis_complete", detail: { source: "playbook", top_cause: "worker_stalled", fallback_reason: "no model configured" } },
    { id: 3, ts: "2026-10-13T06:30:06+00:00", actor: "policy", action: "state_changed", detail: { from: "deciding", to: "awaiting_approval" } },
  ],
  evidence: [
    { ref: "E1", tool: "detector.signal", args: { rule: "step_failure" }, result: { summary: "Order never confirmed" }, created_at: "2026-10-13T06:30:00+00:00" },
    { ref: "E2", tool: "metrics.queue_depth", args: {}, result: { depth: 14, consumers: 0 }, created_at: "2026-10-13T06:30:02+00:00" },
  ],
  hypotheses: [
    { rank: 1, cause: "Order worker stalled", cause_key: "worker_stalled", confidence: 0.86, supporting: ["E1", "E2"], weakening: [] },
    { rank: 2, cause: "Payment gateway degraded", cause_key: "gateway_degraded", confidence: 0.09, supporting: [], weakening: ["E1"] },
  ],
  actions: [
    { id: 1, type: "restart_service", target: "order-worker", risk: "medium", mode: "auto", state: "proposed", rollback: "Redeploy the previous revision", created_at: "2026-10-13T06:30:06+00:00", approved_by: null },
  ],
  verifications: [],
};

export const FIXTURE_EDGE: EdgeStatusView = {
  node: "fulfillment-hub-01",
  seen: true,
  online: true,
  last_seen: "2026-10-13T06:30:00+00:00",
  heartbeat_age_s: 1.2,
  uptime_s: 518400,
  temp_c: 74.5,
  rssi_dbm: -58,
  fan_rpm: 0,
  temp_limit_c: 70,
  latest: { node: "fulfillment-hub-01", uptime_s: 518400, temp_c: 74.5, rssi_dbm: -58, fan_rpm: 0, fault: null },
  history: Array.from({ length: 30 }, (_, i) => ({
    ago_s: (29 - i) * 2,
    temp_c: 41 + i * 1.2,
    rssi_dbm: -58,
    fan_rpm: i < 8 ? 4200 : 0,
  })),
};

export function fixtureFor(path: string): unknown {
  if (path.startsWith("/edge/status")) return FIXTURE_EDGE;
  if (path === "/incidents") return [FIXTURE_DETAIL] satisfies IncidentView[];
  if (path.startsWith("/incidents/")) return FIXTURE_DETAIL;
  if (path.startsWith("/audit")) {
    return FIXTURE_DETAIL.timeline.map((t) => ({ ...t, incident_id: FIXTURE_DETAIL.id, is_demo: true })) satisfies AuditEventView[];
  }
  return undefined;
}
