import { actionName, CAUSE_LABEL, journeyName, rel, riskOf, secondsBetween, secs } from "../lib/format";
import { riskTone, stateLabel, stateTone } from "../lib/incidentState";
import type { IncidentDetailView } from "../lib/types";
import { ApprovalCard } from "./ApprovalCard";
import { HypothesisList } from "./HypothesisList";
import { StageSteps } from "./StageSteps";
import { StatusPill } from "./StatusPill";
import { TraceList } from "./TraceList";

const ACT_STATE: Record<string, [string, "ok" | "warn" | "crit" | "acc" | ""]> = {
  proposed: ["Proposed", ""],
  awaiting_approval: ["Awaiting approval", "warn"],
  approved: ["Approved", "ok"],
  done: ["Done", "ok"],
  rolled_back: ["Rolled back", "warn"],
  denied: ["Denied", "crit"],
  blocked: ["Blocked", "crit"],
  skipped: ["Skipped", "warn"],
  failed: ["Failed", "crit"],
};

const KIND: Record<string, string> = {
  detector: "k-detector", agent: "k-agent", policy: "k-policy", human: "k-human", executor: "k-executor",
  verifier: "k-verifier", harness: "k-harness",
};

function timelineText(t: IncidentDetailView["timeline"][number]): string {
  const d = t.detail as Record<string, unknown>;
  const s = (k: string) => (typeof d[k] === "string" ? (d[k] as string) : "");
  switch (t.action) {
    case "incident_opened": return `Detected by rule ${s("rule")}: ${s("summary")}`;
    case "state_changed": return `Moved to ${stateLabel(s("to")).toLowerCase()}${s("reason") ? `: ${s("reason")}` : ""}`;
    case "investigation_started": return "Specialists dispatched";
    case "diagnosis_complete": return `Top cause: ${CAUSE_LABEL[s("top_cause")] ?? s("top_cause")} (${Math.round(Number(d.confidence ?? 0) * 100)}%), by the ${s("source") === "llm" ? "model" : "rule-based playbook"}`;
    case "policy_decision": return `Policy: ${actionName(s("action"))} on ${s("target")}, ${s("mode") === "auto" ? "auto-approved" : s("mode") === "approval" ? "needs human approval" : "blocked"}`;
    case "action_executed": return `Completed: ${actionName(s("action"))} on ${s("target")}`;
    case "action_rolled_back": return `Rolled back: ${actionName(s("action"))}`;
    case "approved": return `Approved by ${s("operator")}`;
    case "denied": return `Denied by ${s("operator")}`;
    case "verification_run": return `Re-run ${String(d.run)} of 3: ${d.passed ? "passed" : "failed"}`;
    case "escalated": return `Escalated to on-call: ${s("reason")}`;
    default: return t.action.replaceAll("_", " ");
  }
}

export function IncidentDetail({ incident: i }: { incident: IncidentDetailView }) {
  const top = i.hypotheses[0];
  const ttr = i.closed_at && (i.state === "resolved" || i.state === "mitigated") ? secondsBetween(i.opened_at, i.closed_at) : null;
  const sig = i.signals as { first_summary?: string; last_summary?: string; details?: Record<string, unknown> };
  const diagnosis = i.timeline.find((t) => t.action === "diagnosis_complete");

  return (
    <div className="detail" aria-label={`Incident ${i.id}`}>
      <div className="card">
        <div className="pills">
          <span className="mono muted">#{i.id}</span>
          <StatusPill status={riskTone(riskOf(i, i.actions))}>Risk {riskOf(i, i.actions)}</StatusPill>
          <StatusPill status={stateTone(i.state)}>{stateLabel(i.state)}</StatusPill>
          {i.is_demo && <StatusPill>Sample</StatusPill>}
        </div>
        <h2 className="inc-h">{i.title}</h2>
        <dl className="meta">
          <div><dt>Journey</dt><dd>{journeyName(i.journey)}</dd></div>
          <div><dt>Detected by</dt><dd className="mono">{i.rule}</dd></div>
          <div><dt>Time to resolve</dt><dd className="mono">{ttr != null ? secs(ttr) : "—"}</dd></div>
        </dl>
        <StageSteps stage={i.stage} state={i.state} failedStage={i.failed_stage} />
        {(sig.first_summary || sig.last_summary) && (
          <ul className="signals">
            {sig.first_summary && <li>{sig.first_summary}</li>}
            {sig.last_summary && sig.last_summary !== sig.first_summary && <li>{sig.last_summary}</li>}
          </ul>
        )}
        {i.pending_action && (
          <ApprovalCard incidentId={i.id} action={i.pending_action} likelyCause={i.top_cause} confidence={top?.confidence} />
        )}
        {i.is_demo && <p className="muted small" style={{ marginTop: 10 }}>Sample history. Not a real event and excluded from the scorecard.</p>}
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h2 style={{ marginBottom: 8 }}>Timeline</h2>
          <ol className="tl">
            {i.timeline.map((t) => (
              <li key={t.id} className={KIND[t.actor] ?? ""}>
                <span className="mono t">{rel(secondsBetween(i.opened_at, t.ts))}</span>
                <i />
                <span>{timelineText(t)}</span>
              </li>
            ))}
          </ol>
        </div>
        <div className="card">
          <h2 style={{ marginBottom: 12 }}>Root-cause hypotheses</h2>
          <HypothesisList hypotheses={i.hypotheses} investigating={i.state === "investigating"} />
          {diagnosis && (
            <p className="muted small" style={{ marginTop: 12 }}>
              Diagnosed by {diagnosis.detail.source === "llm" ? "the model" : "the rule-based playbook"}
              {diagnosis.detail.source !== "llm" && typeof diagnosis.detail.fallback_reason === "string"
                ? ` (${diagnosis.detail.fallback_reason})` : ""}.
            </p>
          )}
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h2 style={{ marginBottom: 10 }}>Investigation trace</h2>
          <TraceList evidence={i.evidence} openedAt={i.opened_at} />
        </div>
        <div className="card">
          <h2 style={{ marginBottom: 12 }}>Recovery and verification</h2>
          {i.actions.length ? (
            <ul className="acts">
              {i.actions.map((a) => {
                const [label, tone] = ACT_STATE[a.state] ?? [a.state, ""];
                return (
                  <li key={a.id}>
                    <div className="act-h">
                      <strong>{actionName(a.type)}</strong>
                      <StatusPill status={tone}>{label}</StatusPill>
                    </div>
                    <p className="muted">Target <span className="mono">{a.target}</span></p>
                    <div className="pills">
                      <StatusPill status={riskTone(a.risk)}>Risk {a.risk}</StatusPill>
                      <StatusPill>{a.mode === "auto" ? "Auto-approved" : a.mode === "approval" ? "Needs approval" : "Blocked"}</StatusPill>
                      {a.approved_by && <StatusPill>Approved by {a.approved_by}</StatusPill>}
                    </div>
                    <p className="muted small">Rollback: {a.rollback}</p>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="empty">No action chosen yet.</p>
          )}
          <h3>Verification</h3>
          {i.verifications.length ? (
            <ul className="ver">
              {i.verifications.map((v) => (
                <li key={v.run_number}>
                  <StatusPill status={v.passed ? "ok" : "crit"}>{v.passed ? "Passed" : "Failed"}</StatusPill>
                  <span>Re-run {v.run_number} of 3</span>
                  <span className="mono muted">{v.ms} ms</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty" style={{ marginTop: 6 }}>The affected journey is re-run 3 times after recovery. Closing needs 3 passes in a row.</p>
          )}
        </div>
      </div>
    </div>
  );
}
