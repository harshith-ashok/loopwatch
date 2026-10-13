import type { Status } from "../components/StatusPill";

const STAT: Record<string, [string, Status]> = {
  investigating: ["Investigating", "acc"],
  deciding: ["Deciding", "acc"],
  awaiting_approval: ["Awaiting approval", "warn"],
  acting: ["Recovering", "acc"],
  verifying: ["Verifying", "acc"],
  resolved: ["Resolved", "ok"],
  mitigated: ["Mitigated", "ok"],
  escalated: ["Escalated", "crit"],
  false_positive: ["False positive", ""],
  cancelled: ["Cancelled", ""],
};

export const stateLabel = (s: string) => STAT[s]?.[0] ?? s;
export const stateTone = (s: string): Status => STAT[s]?.[1] ?? "";
export const riskTone = (r: string): Status => ({ low: "ok", medium: "warn", high: "crit" })[r] as Status ?? "";
