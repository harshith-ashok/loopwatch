import { stateLabel, stateTone } from "../lib/incidentState";
import { StatusPill } from "./StatusPill";
import { HypothesisList } from "./HypothesisList";
import { ApprovalCard } from "./ApprovalCard";
import { StageSteps } from "./StageSteps";
import { TraceList } from "./TraceList";
import type { IncidentDetailView } from "../lib/types";

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="space-y-2">
    <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">{title}</h3>
    {children}
  </section>
);

export function IncidentDetail({ incident: i }: { incident: IncidentDetailView }) {
  const diagnosis = i.timeline.find((t) => t.action === "diagnosis_complete");
  return (
    <article className="space-y-6" aria-label={`Incident ${i.id}`}>
      <header className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h2 className="text-lg font-semibold">
            #{i.id} {i.title}
          </h2>
          <StatusPill status={stateTone(i.state)}>{stateLabel(i.state)}</StatusPill>
        </div>
        <StageSteps stage={i.stage} state={i.state} />
        {i.pending_action && (
          <ApprovalCard incidentId={i.id} action={i.pending_action} likelyCause={i.top_cause} />
        )}
        {i.is_demo && <p className="text-xs text-muted">Sample data. Not a real event and excluded from the scorecard.</p>}
        <p className="text-sm text-muted">
          Detected by rule <span className="font-mono">{i.rule}</span> at{" "}
          {new Date(i.opened_at).toLocaleTimeString()}
        </p>
      </header>

      <Section title="Timeline">
        <ol className="space-y-1.5 border-l border-border pl-4 text-sm">
          {i.timeline.map((t) => (
            <li key={t.id}>
              <span className="font-mono text-xs text-muted">{new Date(t.ts).toLocaleTimeString()}</span>{" "}
              <span className="font-medium">{t.actor}</span> {t.action.replaceAll("_", " ")}
              {typeof t.detail.to === "string" && <span className="text-muted"> → {stateLabel(t.detail.to)}</span>}
            </li>
          ))}
        </ol>
      </Section>

      <Section title="Likely causes">
        <HypothesisList hypotheses={i.hypotheses} investigating={i.state === "investigating"} />
        {diagnosis && (
          <p className="text-xs text-muted">
            Diagnosed by {diagnosis.detail.source === "llm" ? "the model" : "the rule-based playbook"}
            {diagnosis.detail.source !== "llm" && typeof diagnosis.detail.fallback_reason === "string"
              ? ` (${diagnosis.detail.fallback_reason})`
              : ""}
            .
          </p>
        )}
      </Section>

      <Section title="What was checked">
        <TraceList evidence={i.evidence} />
      </Section>

      <Section title="Actions">
        {i.actions.length === 0 ? (
          <p className="text-sm text-muted">No action proposed yet.</p>
        ) : (
          <ul className="space-y-2">
            {i.actions.map((a) => (
              <li key={a.id} className="rounded-md border border-border p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono">
                    {a.type} → {a.target}
                  </span>
                  <span className="text-muted">
                    {a.risk} risk · {a.mode} · {a.state.replaceAll("_", " ")}
                  </span>
                </div>
                <p className="mt-1 text-muted">Rollback: {a.rollback}</p>
                {a.approved_by && <p className="mt-1 text-muted">Approved by {a.approved_by}</p>}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Verification">
        {i.verifications.length === 0 ? (
          <p className="text-sm text-muted">Not verified yet. Closing needs 3 passing runs in a row.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {i.verifications.map((v) => (
              <li key={v.run_number} className="flex justify-between">
                <span className={v.passed ? "text-ok" : "text-crit"}>
                  <span aria-hidden="true">{v.passed ? "✓" : "✕"} </span>Run {v.run_number}{" "}
                  {v.passed ? "passed" : "failed"}
                </span>
                <span className="font-mono text-muted">{v.ms} ms</span>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </article>
  );
}
