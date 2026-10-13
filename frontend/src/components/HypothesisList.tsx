import type { HypothesisView } from "../lib/types";

export function HypothesisList({
  hypotheses,
  investigating = false,
}: {
  hypotheses: HypothesisView[];
  investigating?: boolean;
}) {
  if (hypotheses.length === 0) {
    return (
      <p className="text-sm text-muted" role={investigating ? "status" : undefined}>
        {investigating
          ? "Specialists are collecting evidence. Likely causes appear here when they finish."
          : "No hypotheses were produced for this incident."}
      </p>
    );
  }
  return (
    <ol className="space-y-3">
      {hypotheses.map((h) => {
        const pct = Math.round(h.confidence * 100);
        return (
          <li key={h.rank} className="rounded-md border border-border p-3">
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-medium">
                {h.rank}. {h.cause}
              </span>
              <span className="font-mono text-sm">{pct}%</span>
            </div>
            <div
              role="progressbar"
              aria-label={`Confidence for ${h.cause}`}
              aria-valuenow={pct}
              aria-valuemin={0}
              aria-valuemax={100}
              className="mt-2 h-1.5 rounded-full bg-surface-2"
            >
              <div className="h-1.5 rounded-full bg-accent" style={{ width: `${pct}%` }} />
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
              {h.supporting.map((r) => (
                <span key={`s-${r}`} className="rounded bg-ok-bg px-1.5 py-0.5 font-mono text-ok">
                  + {r}
                </span>
              ))}
              {h.weakening.map((r) => (
                <span key={`w-${r}`} className="rounded bg-warn-bg px-1.5 py-0.5 font-mono text-warn">
                  − {r}
                </span>
              ))}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
