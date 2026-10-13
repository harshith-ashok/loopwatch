import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiPost } from "../lib/api";
import { hms, JOURNEY_VIA, stepService } from "../lib/format";
import type { JourneyView } from "../lib/types";
import { journeyLabel, journeyTone } from "../lib/journeyState";
import { Sparkline } from "./Sparkline";
import { StatusPill } from "./StatusPill";

export function JourneyCard({ journey: j }: { journey: JourneyView }) {
  const qc = useQueryClient();
  const run = useMutation({
    mutationFn: () => apiPost<JourneyView>(`/journeys/${j.id}/run`),
    onSuccess: () => {
      for (const k of ["journeys", "overview"]) void qc.invalidateQueries({ queryKey: [k] });
    },
  });
  const tone = journeyTone(j);

  return (
    <article className="card" aria-label={`${j.label} journey`}>
      <div className="card-h">
        <h2>{j.label}</h2>
        <StatusPill status={tone}>{journeyLabel(j)}</StatusPill>
      </div>
      <p className="muted small">
        {JOURNEY_VIA[j.id] ?? "HTTP probe"}
        {j.latest && (
          <>
            , last run <span className="mono">{hms(j.latest.started_at)}</span>
          </>
        )}
      </p>
      <ol className="jsteps">
        {(j.latest?.steps ?? []).map((s) => (
          <li key={s.id} className={s.status === "failed" ? "bad" : s.status === "skipped" ? "skip" : ""}>
            <span className="si" />
            <span className="sn">
              {s.label}
              <small>{s.status === "failed" && s.detail ? s.detail : stepService(s)}</small>
              <span className="sr-only"> ({s.status})</span>
            </span>
            <span className="mono ms">{s.status === "skipped" ? "skipped" : s.status === "failed" ? "failed" : `${s.ms} ms`}</span>
          </li>
        ))}
        {!j.latest && <li className="skip"><span className="si" /><span className="sn">No runs recorded yet</span><span /></li>}
      </ol>
      <div className="jfoot">
        <Sparkline values={j.history_ms} width={200} height={38} tone={j.status === "failed" ? "crit" : "acc"}
          label={`${j.label} response time over the last ${j.history_ms.length} runs`} />
        <button type="button" className="btn" disabled={run.isPending} onClick={() => run.mutate()}>
          {run.isPending ? "Running…" : "Run now"}
        </button>
      </div>
      {run.isError && <p className="small err">Could not run this journey.</p>}
    </article>
  );
}
