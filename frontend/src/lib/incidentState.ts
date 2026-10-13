import type { Status } from "../components/StatusPill";

const STATE_LABEL: Record<string, string> = {
  investigating: "Investigating",
  deciding: "Deciding",
  awaiting_approval: "Awaiting approval",
  acting: "Acting",
  verifying: "Verifying",
  resolved: "Resolved",
  mitigated: "Mitigated",
  escalated: "Escalated",
  false_positive: "False positive",
  cancelled: "Cancelled",
};

export function stateTone(state: string): Status {
  if (state === "resolved") return "ok";
  if (state === "mitigated" || state === "awaiting_approval") return "warn";
  if (state === "escalated") return "crit";
  if (state === "cancelled" || state === "false_positive") return "neutral";
  return "warn";
}

export const stateLabel = (s: string) => STATE_LABEL[s] ?? s;
