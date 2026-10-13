import type { HypothesisView } from "../lib/types";
import { StatusPill } from "./StatusPill";

export function HypothesisList({
  hypotheses,
  investigating = false,
}: {
  hypotheses: HypothesisView[];
  investigating?: boolean;
}) {
  if (hypotheses.length === 0) {
    return (
      <p className="empty" role={investigating ? "status" : undefined}>
        {investigating
          ? "Specialists are collecting evidence. Likely causes appear here when they finish."
          : "No hypotheses were produced for this incident."}
      </p>
    );
  }
  return (
    <ul className="hyps">
      {hypotheses.map((h, i) => {
        const pct = Math.round(h.confidence * 100);
        return (
          <li key={h.rank}>
            <div className="hyp-h">
              <strong>{h.cause}</strong>
              <span className="mono">{pct}%</span>
            </div>
            <div className="bar" role="progressbar" aria-label={`Confidence for ${h.cause}`} aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
              <i className={i === 0 ? "top" : ""} style={{ width: `${pct}%` }} />
            </div>
            <div className="refs">
              {i === 0 && <StatusPill status="acc">Selected</StatusPill>}
              {h.supporting.map((r) => (
                <span key={`s-${r}`} className="chip pos">{r} supports</span>
              ))}
              {h.weakening.map((r) => (
                <span key={`w-${r}`} className="chip neg">{r} weakens</span>
              ))}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
