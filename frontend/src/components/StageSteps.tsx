import { STAGES, TERMINAL_STATES, type Stage } from "../lib/types";

const LABEL: Record<Stage, string> = {
  detect: "Detect",
  investigate: "Investigate",
  decide: "Decide",
  act: "Act",
  verify: "Verify",
};

const WAITING_STATES = new Set(["awaiting_approval"]);

/** Five-step progress bar. State is conveyed by text and glyph, not color alone. */
export function StageSteps({ stage, state }: { stage: string; state: string }) {
  const current = STAGES.indexOf(stage as Stage);
  const done = TERMINAL_STATES.includes(state);
  const failedEnd = state === "escalated" || state === "cancelled" || state === "false_positive";

  return (
    <ol className="flex flex-wrap gap-2" aria-label="Incident stages">
      {STAGES.map((s, i) => {
        const complete = done ? !(failedEnd && i >= current) || i < current : i < current;
        const isCurrent = !done && i === current;
        const glyph = complete ? "✓" : isCurrent ? (WAITING_STATES.has(state) ? "⏸" : "●") : "○";
        const status = complete ? "done" : isCurrent ? (WAITING_STATES.has(state) ? "waiting" : "in progress") : "pending";
        return (
          <li
            key={s}
            aria-current={isCurrent ? "step" : undefined}
            className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-sm ${
              isCurrent ? "border-accent font-semibold text-text" : "border-border text-muted"
            } ${complete ? "text-ok" : ""}`}
          >
            <span aria-hidden="true">{glyph}</span>
            {LABEL[s]}
            <span className="sr-only"> ({status})</span>
          </li>
        );
      })}
    </ol>
  );
}
