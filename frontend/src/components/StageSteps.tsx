import { stageStates, type St } from "../lib/stages";

const LABEL: Record<string, string> = { detect: "Detect", investigate: "Investigate", decide: "Decide", act: "Act", verify: "Verify" };
const SR: Record<St, string> = { done: "done", active: "in progress", wait: "waiting for approval", fail: "failed", todo: "not reached" };

/** Five-step bar. Each step also says its state in text for screen readers. */
export function StageSteps({ stage, state, failedStage }: { stage: string; state: string; failedStage?: string | null }) {
  return (
    <ol className="steps" aria-label="Incident stages">
      {stageStates(stage, state, failedStage).map((s) => (
        <li key={s.key} className={s.state} aria-current={s.state === "active" || s.state === "wait" ? "step" : undefined}>
          <i />
          <span>
            {LABEL[s.key]}
            <span className="sr-only"> ({SR[s.state]})</span>
          </span>
        </li>
      ))}
    </ol>
  );
}
