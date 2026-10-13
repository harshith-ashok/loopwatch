import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiPost } from "../lib/api";
import type { JourneyView } from "../lib/types";
import { Sparkline } from "./Sparkline";
import { StatusPill } from "./StatusPill";

const STEP_GLYPH = { ok: "●", failed: "✕", skipped: "–" } as const;
const STEP_COLOR = { ok: "text-ok", failed: "text-crit", skipped: "text-muted" } as const;

export function JourneyCard({ journey, showSteps = true }: { journey: JourneyView; showSteps?: boolean }) {
  const qc = useQueryClient();
  const run = useMutation({
    mutationFn: () => apiPost<JourneyView>(`/journeys/${journey.id}/run`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["journeys"] });
      void qc.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  const pill =
    journey.status === "ok" ? (
      <StatusPill status="ok">Working</StatusPill>
    ) : journey.status === "failed" ? (
      <StatusPill status="crit">Broken</StatusPill>
    ) : (
      <StatusPill status="neutral">No runs yet</StatusPill>
    );

  return (
    <article className="rounded-lg border border-border bg-surface p-4" aria-label={`${journey.label} journey`}>
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">{journey.label}</h2>
        {pill}
      </header>

      <div className="mt-3 flex items-center justify-between gap-3">
        <Sparkline
          values={journey.history_ms}
          ok={journey.history_ok}
          label={`${journey.label} response time over the last ${journey.history_ms.length} runs`}
        />
        <div className="text-right font-mono text-sm">
          <div>{journey.latest ? `${journey.latest.total_ms} ms` : "–"}</div>
          {journey.baseline_mean_ms !== null && (
            <div className="text-xs text-muted">usual {Math.round(journey.baseline_mean_ms)} ms</div>
          )}
        </div>
      </div>

      {showSteps && journey.latest && (
        <ol className="mt-3 space-y-1 text-sm">
          {journey.latest.steps.map((s) => (
            <li key={s.id} className="flex items-baseline justify-between gap-2">
              <span className={STEP_COLOR[s.status]}>
                <span aria-hidden="true">{STEP_GLYPH[s.status]} </span>
                {s.label}
                <span className="sr-only"> ({s.status})</span>
              </span>
              <span className="font-mono text-xs text-muted">
                {s.status === "skipped" ? "skipped" : `${s.ms} ms`}
              </span>
            </li>
          ))}
        </ol>
      )}
      {journey.latest?.steps.find((s) => s.status === "failed")?.detail && (
        <p className="mt-2 text-sm text-crit">
          {journey.latest.steps.find((s) => s.status === "failed")?.detail}
        </p>
      )}

      <button
        type="button"
        onClick={() => run.mutate()}
        disabled={run.isPending}
        className="mt-4 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-surface-2 disabled:opacity-60"
      >
        {run.isPending ? "Running…" : "Run now"}
      </button>
      {run.isError && <p className="mt-2 text-sm text-crit">Could not run this journey.</p>}
    </article>
  );
}
