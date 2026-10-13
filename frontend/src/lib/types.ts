export interface StepView {
  id: string;
  label: string;
  status: "ok" | "failed" | "skipped";
  ms: number;
  error_kind: string | null;
  detail: string | null;
}

export interface JourneyView {
  id: string;
  label: string;
  status: "ok" | "failed" | "unknown";
  latest: {
    started_at: string;
    ok: boolean;
    total_ms: number;
    failed_step: string | null;
    steps: StepView[];
  } | null;
  history_ms: number[];
  history_ok: boolean[];
  baseline_mean_ms: number | null;
}

export interface OverviewView {
  journeys_total: number;
  journeys_healthy: number;
  open_incidents: number;
  journeys: JourneyView[];
}

export interface IncidentView {
  id: number;
  title: string;
  journey: string;
  state: string;
  stage: string;
  failed_stage: string | null;
  rule: string;
  signals: Record<string, unknown>;
  opened_at: string;
  closed_at: string | null;
  is_demo: boolean;
  top_cause: string | null;
  pending_action: PendingActionView | null;
}

export interface PendingActionView {
  id: number;
  type: string;
  target: string;
  risk: string;
  rollback: string;
}

export interface EvidenceView {
  ref: string;
  tool: string;
  args: Record<string, unknown>;
  result: Record<string, unknown>;
  created_at: string;
}

export interface HypothesisView {
  rank: number;
  cause: string;
  cause_key: string;
  confidence: number;
  supporting: string[];
  weakening: string[];
}

export interface ActionView {
  id: number;
  type: string;
  target: string;
  risk: string;
  mode: string;
  state: string;
  rollback: string;
  created_at: string;
  approved_by: string | null;
}

export interface VerificationView {
  run_number: number;
  passed: boolean;
  ms: number;
  created_at: string;
}

export interface TimelineEventView {
  id: number;
  ts: string;
  actor: string;
  action: string;
  detail: Record<string, unknown>;
}

export interface IncidentDetailView extends IncidentView {
  timeline: TimelineEventView[];
  evidence: EvidenceView[];
  hypotheses: HypothesisView[];
  actions: ActionView[];
  verifications: VerificationView[];
}

export const STAGES = ["detect", "investigate", "decide", "act", "verify"] as const;
export type Stage = (typeof STAGES)[number];

export const TERMINAL_STATES = ["resolved", "mitigated", "escalated", "false_positive", "cancelled"];

export interface AuditEventView {
  id: number;
  ts: string;
  actor: string;
  incident_id: number | null;
  action: string;
  detail: Record<string, unknown>;
  is_demo: boolean;
}

export interface EdgeSample {
  ago_s: number;
  temp_c: number;
  rssi_dbm: number;
  fan_rpm: number;
}

export interface EdgeStatusView {
  node: string;
  seen: boolean;
  online: boolean;
  last_seen: string | null;
  heartbeat_age_s: number | null;
  uptime_s: number | null;
  temp_c: number | null;
  rssi_dbm: number | null;
  fan_rpm: number | null;
  temp_limit_c: number;
  latest: Record<string, unknown> | null;
  history: EdgeSample[];
}

export interface PolicyActionView {
  name: string;
  risk: "low" | "medium" | "high";
  default_mode: string;
  mode: string;
  targets: string[];
  rollback: string;
}

export interface PolicyView {
  paused: boolean;
  budget: number;
  pace: string;
  pace_options: string[];
  agent_mode: string;
  actions: PolicyActionView[];
}

export interface MetricView {
  value: number | null;
  n: number;
  definition: string;
}

export interface ScoreRow {
  id: number;
  title: string;
  scenario: string | null;
  true_cause: string | null;
  top_cause: string | null;
  correct: boolean | null;
  state: string;
  detection_latency_s: number | null;
  time_to_close_s: number | null;
}

export interface ComparisonView {
  recorded_at: string;
  timing_note: string;
  runs_per_scenario: number;
  control_runs: number;
  decoy_runs: number;
  modes: Record<string, Record<string, { value: number | null; n: number }>>;
}

export interface ScoreView {
  metrics: Record<string, MetricView>;
  incidents: ScoreRow[];
  incidents_scored: number;
  demo_incidents_excluded: number;
  generated_at: string;
  comparison: ComparisonView | null;
}
