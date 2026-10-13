import type { AuditEventView, IncidentView, StepView } from "./types";

const p2 = (n: number) => String(n).padStart(2, "0");

export const hms = (iso: string | Date) => {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return `${p2(d.getHours())}:${p2(d.getMinutes())}:${p2(d.getSeconds())}`;
};
export const rel = (s: number | null) => (s == null ? "—" : `+${Math.floor(s / 60)}:${p2(Math.floor(s % 60))}`);
export const secs = (s: number | null | undefined) =>
  s == null ? "—" : `${s < 10 ? s.toFixed(1) : String(Math.round(s))} s`;
export const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}%`);
export const dur = (s: number | null) => {
  if (s == null) return "—";
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  return d ? `${d} d ${h} h` : h ? `${h} h ${m} m` : `${m} m`;
};
export const fmtTs = (iso: string) =>
  new Date(iso).toLocaleString([], { hour12: false, month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" });

export const secondsBetween = (a: string, b: string) => (new Date(b).getTime() - new Date(a).getTime()) / 1000;

/** Display names for the five catalog actions. */
export const ACTION_NAME: Record<string, string> = {
  retry_operation: "Retry failed operation",
  switch_endpoint: "Switch to fallback endpoint",
  restart_service: "Restart service",
  open_ticket: "Open incident ticket",
  power_cycle_device: "Power-cycle edge device",
};
export const actionName = (t: string) => ACTION_NAME[t] ?? t;

export const CAUSE_LABEL: Record<string, string> = {
  worker_stalled: "Order worker stalled, no active consumers",
  gateway_degraded: "Primary payment gateway degraded",
  cooling_fault: "Cooling fault on the edge node",
  link_lost: "Edge node link lost",
  unknown: "Cause not identified",
};

export const JOURNEY_VIA: Record<string, string> = {
  login: "HTTP probe",
  checkout: "HTTP probe",
  payment: "HTTP probe",
  order: "HTTP probe",
  edge: "Edge telemetry",
};
export const journeyName = (id: string) =>
  ({ login: "Login", checkout: "Checkout", payment: "Payment", order: "Order confirmation", edge: "Edge node" })[id] ?? id;

/** Which service owns a probe step, shown under the step name. */
export const STEP_SERVICE: Record<string, string> = {
  open_shop: "shop-web",
  login: "auth-api",
  add_to_cart: "shop-api",
  checkout: "shop-api",
  pay: "payments",
  confirm: "order-worker",
  ack: "fulfillment-hub-01",
};
export const stepService = (s: StepView) => STEP_SERVICE[s.id] ?? "";

/** Which specialist a tool belongs to. */
export const TOOL_AGENT: Record<string, string> = {
  "detector.signal": "Detector",
  "db.payments": "Transactions",
  "db.orders": "Transactions",
  "traces.slowest": "Transactions",
  "metrics.queue_depth": "App and logs",
  "logs.search": "App and logs",
  "device.health": "Device",
  "device.telemetry": "Device",
  "network.ping": "Device",
  "memory.similar": "Past incidents",
};

export function riskOf(i: Pick<IncidentView, "pending_action">, actions?: { risk: string }[]): string {
  const rank = { low: 0, medium: 1, high: 2 } as Record<string, number>;
  const all = [...(actions ?? []).map((a) => a.risk), ...(i.pending_action ? [i.pending_action.risk] : [])];
  return all.reduce((m, r) => ((rank[r] ?? 0) > (rank[m] ?? 0) ? r : m), "low");
}

/** One line of plain text for an audit event. Detail values are data, rendered as text. */
export function describeAudit(e: AuditEventView): string {
  const d = e.detail as Record<string, unknown>;
  const s = (k: string) => (typeof d[k] === "string" ? (d[k] as string) : undefined);
  switch (e.action) {
    case "incident_opened":
      return `Opened incident: ${s("summary") ?? s("rule") ?? ""}`.trim();
    case "state_changed":
      return `Incident moved to ${String(s("to") ?? "").replaceAll("_", " ")}${s("reason") ? ` (${s("reason")})` : ""}`;
    case "diagnosis_complete":
      return `Diagnosed as ${CAUSE_LABEL[s("top_cause") ?? ""] ?? s("top_cause")} using the ${s("source") === "llm" ? "model" : "rule-based playbook"}`;
    case "policy_decision":
      return `${actionName(s("action") ?? "")} on ${s("target")}: ${s("mode") === "auto" ? "auto-approved" : s("mode") === "approval" ? "approval required" : "blocked"}`;
    case "action_executed":
      return `Completed ${actionName(s("action") ?? "")} on ${s("target")}`;
    case "action_rolled_back":
      return `Rolled back ${actionName(s("action") ?? "")}`;
    case "approved":
      return `${s("operator") ?? "Operator"} approved ${actionName(s("action") ?? "")}`;
    case "denied":
      return `${s("operator") ?? "Operator"} denied ${actionName(s("action") ?? "")}`;
    case "verification_run":
      return `Re-run ${String(d.run)} of 3: ${d.passed ? "passed" : "failed"}`;
    case "escalated":
      return `Escalated: ${s("reason") ?? ""}`;
    case "fault_injected":
      return `Fault injected: ${s("scenario")}`;
    case "faults_reset":
      return "System reset: all journeys and the edge node are healthy";
    default:
      return e.action.replaceAll("_", " ");
  }
}

/** Colour class for the actor tag in the feed. */
export const actorTone = (actor: string) =>
  ({ detector: "crit", agent: "agent", policy: "warn", human: "human", executor: "agent", verifier: "ok" })[actor] ?? "";
