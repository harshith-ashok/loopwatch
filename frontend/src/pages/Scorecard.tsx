import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Kpi } from "../components/Kpi";
import { PageHead } from "../components/PageHead";
import { StatusPill } from "../components/StatusPill";
import { apiGet } from "../lib/api";
import { CAUSE_LABEL, pct, secs } from "../lib/format";
import { stateLabel, stateTone } from "../lib/incidentState";
import type { ScoreView } from "../lib/types";

const LABELS: Record<string, { label: string; sub: string; unit: "s" | "%" }> = {
  detection_latency_s: { label: "Detection latency", sub: "Fault injected to incident opened", unit: "s" },
  root_cause_accuracy: { label: "Root-cause accuracy", sub: "Top hypothesis matches the injected fault", unit: "%" },
  recovery_success: { label: "Recovery success", sub: "Resolved or mitigated", unit: "%" },
  false_positive_rate: { label: "False-positive rate", sub: "Incidents with no real fault", unit: "%" },
  mttr_s: { label: "Mean time to resolve", sub: "Opened to verified recovery", unit: "s" },
  unsafe_action_rate: { label: "Unsafe action rate", sub: "High risk unapproved, or wrong for the cause", unit: "%" },
};
const MODES: Record<string, string> = { loopwatch: "Loopwatch", alert_only: "Alert only", blind_remediation: "Blind restart" };
const show = (key: string, v: number | null) => (v === null ? "—" : LABELS[key]?.unit === "%" ? pct(v) : secs(v));

export default function Scorecard() {
  const { data, isPending, isError } = useQuery({ queryKey: ["score"], queryFn: () => apiGet<ScoreView>("/score") });
  if (isPending) return <p className="empty">Loading scorecard…</p>;
  if (isError || !data) return <p className="err" role="alert">Could not load the scorecard. Is the backend running?</p>;
  const cmp = data.comparison;

  return (
    <section className="view">
      <PageHead title="Scorecard"
        sub={`Measured from injected faults with known causes. ${data.incidents_scored} incident(s) scored${data.demo_incidents_excluded ? `, ${data.demo_incidents_excluded} sample incident(s) excluded` : ""}.`} />
      {data.incidents_scored === 0 ? (
        <div className="card empty">Nothing to score yet. Inject a fault from the Overview page and let the system respond.</div>
      ) : (
        <div className="grid kpis">
          {Object.entries(data.metrics).map(([k, m]) => (
            <Kpi key={k} label={LABELS[k]?.label ?? k} value={show(k, m.value)} hint={`${LABELS[k]?.sub ?? ""} (n=${m.n})`} />
          ))}
        </div>
      )}

      {data.incidents.length > 0 && (
        <div className="card scroll">
          <h2 style={{ marginBottom: 8 }}>Incidents</h2>
          <table className="tbl">
            <thead><tr><th>Incident</th><th>Injected</th><th>True cause</th><th>Diagnosed</th><th>Outcome</th><th>Detected after</th><th>Time to close</th></tr></thead>
            <tbody>
              {data.incidents.map((r) => (
                <tr key={r.id}>
                  <td><Link className="link mono" to={`/incidents/${r.id}`}>#{r.id}</Link></td>
                  <td>{r.scenario ?? "none"}</td>
                  <td>{r.true_cause ? CAUSE_LABEL[r.true_cause] ?? r.true_cause : "—"}</td>
                  <td>{r.top_cause ? <StatusPill status={r.correct === null ? "" : r.correct ? "ok" : "crit"}>{r.correct === null ? r.top_cause : r.correct ? "Correct" : "Missed"}</StatusPill> : "—"}</td>
                  <td><StatusPill status={stateTone(r.state)}>{stateLabel(r.state)}</StatusPill></td>
                  <td className="mono">{secs(r.detection_latency_s)}</td>
                  <td className="mono">{secs(r.time_to_close_s)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card scroll">
        <h2 style={{ marginBottom: 6 }}>Baselines</h2>
        {cmp ? (
          <>
            <p className="muted small" style={{ marginBottom: 8 }}>
              Recorded {new Date(cmp.recorded_at).toLocaleDateString()}: {cmp.runs_per_scenario} runs per scenario, {cmp.control_runs} control,{" "}
              {cmp.decoy_runs} decoy. {cmp.timing_note}
            </p>
            <table className="tbl">
              <thead><tr><th>Metric</th>{Object.keys(cmp.modes).map((m) => <th key={m}>{MODES[m] ?? m}</th>)}</tr></thead>
              <tbody>
                {Object.keys(LABELS).map((k) => (
                  <tr key={k}>
                    <td>{LABELS[k].label}</td>
                    {Object.keys(cmp.modes).map((m) => {
                      const c = cmp.modes[m][k];
                      return <td key={m} className="mono">{c ? show(k, c.value) : "—"}{c && <span className="muted small"> n={c.n}</span>}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <p className="muted">
            No baseline comparison recorded yet. Run the same fault scenarios with "alert only" and with "blind restart" using the
            evaluation harness (see docs/results.md) to show what the agent adds.
          </p>
        )}
      </div>

      <details className="hint">
        <summary>How each number is defined</summary>
        <dl style={{ marginTop: 8, display: "grid", gap: 8 }}>
          {Object.entries(data.metrics).map(([k, m]) => (
            <div key={k}><dt><strong>{LABELS[k]?.label ?? k}</strong></dt><dd>{m.definition}</dd></div>
          ))}
        </dl>
      </details>
    </section>
  );
}
