import { useQuery } from "@tanstack/react-query";
import { Kpi } from "../components/Kpi";
import { apiGet } from "../lib/api";
import type { MetricView, ScoreView } from "../lib/types";

const LABELS: Record<string, { label: string; unit: string }> = {
  detection_latency_s: { label: "Detection latency", unit: " s" },
  root_cause_accuracy: { label: "Root-cause accuracy", unit: "%" },
  recovery_success: { label: "Recovery success", unit: "%" },
  false_positive_rate: { label: "False-positive rate", unit: "%" },
  mttr_s: { label: "Time to resolve", unit: " s" },
  unsafe_action_rate: { label: "Unsafe action rate", unit: "%" },
};

function show(key: string, m: { value: number | null; n: number }): string {
  if (m.value === null) return "–";
  const unit = LABELS[key].unit;
  return unit === "%" ? `${Math.round(m.value * 100)}%` : `${m.value.toFixed(1)}${unit}`;
}

const MODE_NAMES: Record<string, string> = {
  loopwatch: "Loopwatch",
  alert_only: "Alert only",
  blind_remediation: "Blind restart",
};

export default function Scorecard() {
  const { data, isPending, isError } = useQuery({ queryKey: ["score"], queryFn: () => apiGet<ScoreView>("/score") });

  if (isPending) return <p className="text-muted">Loading scorecard…</p>;
  if (isError || !data) return <p className="text-crit">Could not load the scorecard. Is the backend running?</p>;

  const cmp = data.comparison;
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Scorecard</h1>
        <p className="mt-1 text-muted">
          Measured from injected faults with known causes. {data.incidents_scored} incident(s) scored
          {data.demo_incidents_excluded > 0 ? `, ${data.demo_incidents_excluded} sample incident(s) excluded` : ""}.
        </p>
      </header>

      {data.incidents_scored === 0 ? (
        <p className="rounded-lg border border-border bg-surface p-4 text-muted">
          Nothing to score yet. Inject a fault from the Overview page and let the system respond.
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-4 min-[900px]:grid-cols-3">
          {Object.entries(data.metrics).map(([key, m]: [string, MetricView]) => (
            <Kpi key={key} label={LABELS[key]?.label ?? key} value={show(key, m)} hint={`${m.n} sample(s)`} />
          ))}
        </div>
      )}

      {cmp ? (
        <section aria-labelledby="cmp-h" className="space-y-2">
          <h2 id="cmp-h" className="font-semibold">
            Loopwatch versus baselines
          </h2>
          <p className="text-sm text-muted">
            Recorded {new Date(cmp.recorded_at).toLocaleDateString()}: {cmp.runs_per_scenario} runs per scenario,{" "}
            {cmp.control_runs} control, {cmp.decoy_runs} decoy. {cmp.timing_note}
          </p>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-2 text-muted">
                <tr>
                  <th className="px-3 py-2 font-medium">Metric</th>
                  {Object.keys(cmp.modes).map((m) => (
                    <th key={m} className="px-3 py-2 font-medium">
                      {MODE_NAMES[m] ?? m}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.keys(LABELS).map((key) => (
                  <tr key={key} className="border-t border-border">
                    <td className="px-3 py-2">{LABELS[key].label}</td>
                    {Object.keys(cmp.modes).map((m) => {
                      const cell = cmp.modes[m][key];
                      return (
                        <td key={m} className="px-3 py-2 font-mono">
                          {cell ? show(key, cell) : "–"}
                          {cell && <span className="ml-1 text-xs text-muted">n={cell.n}</span>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <p className="text-sm text-muted">No baseline comparison recorded yet. Run the evaluation harness (see docs/results.md).</p>
      )}

      {data.incidents.length > 0 && (
        <section aria-labelledby="inc-h" className="space-y-2">
          <h2 id="inc-h" className="font-semibold">
            Incidents
          </h2>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-2 text-muted">
                <tr>
                  {["#", "Injected", "True cause", "Diagnosed", "State", "Detected in", "Closed in"].map((h) => (
                    <th key={h} className="px-3 py-2 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.incidents.map((r) => (
                  <tr key={r.id} className="border-t border-border">
                    <td className="px-3 py-2 font-mono">{r.id}</td>
                    <td className="px-3 py-2">{r.scenario ?? "none (false positive)"}</td>
                    <td className="px-3 py-2">{r.true_cause ?? "–"}</td>
                    <td className="px-3 py-2">
                      {r.top_cause ?? "–"}
                      {r.correct !== null && <span aria-label={r.correct ? "correct" : "wrong"}> {r.correct ? "✓" : "✕"}</span>}
                    </td>
                    <td className="px-3 py-2">{r.state.replaceAll("_", " ")}</td>
                    <td className="px-3 py-2 font-mono">{r.detection_latency_s ?? "–"}{r.detection_latency_s !== null && " s"}</td>
                    <td className="px-3 py-2 font-mono">{r.time_to_close_s ?? "–"}{r.time_to_close_s !== null && " s"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <details className="text-sm text-muted">
        <summary className="cursor-pointer">How each number is defined</summary>
        <dl className="mt-2 space-y-2">
          {Object.entries(data.metrics).map(([key, m]) => (
            <div key={key}>
              <dt className="font-medium text-text">{LABELS[key]?.label ?? key}</dt>
              <dd>{m.definition}</dd>
            </div>
          ))}
        </dl>
      </details>
    </div>
  );
}
