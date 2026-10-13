import { STAGES } from "./types";

export type St = "done" | "active" | "wait" | "fail" | "todo";

export function stageStates(stage: string, state: string, failedStage?: string | null): { key: string; state: St }[] {
  const idx = STAGES.indexOf(stage as (typeof STAGES)[number]);
  const fin = state === "resolved" || state === "mitigated";
  const bad = state === "escalated";
  const fi = STAGES.indexOf((failedStage ?? stage) as (typeof STAGES)[number]);
  return STAGES.map((key, i) => ({
    key,
    state:
      state === "false_positive" ? "done"
      : state === "cancelled" ? "todo"
      : fin ? "done"
      : bad ? (i < fi ? "done" : i === fi ? "fail" : "todo")
      : i < idx ? "done"
      : i === idx ? (state === "awaiting_approval" ? "wait" : "active")
      : "todo",
  }));
}
