import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiPost } from "../lib/api";
import { actionName, CAUSE_LABEL } from "../lib/format";
import { riskTone } from "../lib/incidentState";
import { getOperator, setOperator } from "../lib/operator";
import type { PendingActionView } from "../lib/types";
import { Icon } from "./Icon";
import { StatusPill } from "./StatusPill";

interface Props {
  incidentId: number;
  action: PendingActionView;
  likelyCause?: string | null;
  confidence?: number | null;
}

/** The approval panel from the reference: what, where, why, and what happens if it fails. */
export function ApprovalCard({ incidentId, action, likelyCause, confidence }: Props) {
  const qc = useQueryClient();
  const [operator, setName] = useState(getOperator);
  const decide = useMutation({
    mutationFn: (verb: "approve" | "deny") => apiPost(`/incidents/${incidentId}/${verb}`, { operator }),
    onSuccess: () => {
      setOperator(operator);
      for (const k of ["incidents", "overview", "audit"]) void qc.invalidateQueries({ queryKey: [k] });
    },
  });

  return (
    <div className="approve" role="alert" aria-label={`Approval needed for incident ${incidentId}`}>
      <div className="approve-h">
        <Icon name="lock" />
        <strong>Approval needed: {actionName(action.type)}</strong>
        <StatusPill status={riskTone(action.risk)}>Risk {action.risk}</StatusPill>
      </div>
      <p>
        Target <span className="mono">{action.target}</span>. Likely cause:{" "}
        {likelyCause ? (CAUSE_LABEL[likelyCause] ?? likelyCause) : "under investigation"}
        {confidence != null ? ` (${Math.round(confidence * 100)}%)` : ""}.
      </p>
      <p className="small muted">If the fix does not hold, the agent will: {action.rollback.replace(/\.$/, "")}.</p>
      <div className="btns">
        <label>
          <span className="sr-only">Your name</span>
          <input className="num-in op-in" value={operator} maxLength={64} onChange={(e) => setName(e.target.value)} />
        </label>
        <button type="button" className="btn primary" disabled={decide.isPending} onClick={() => decide.mutate("approve")}>
          Approve and run
        </button>
        <button type="button" className="btn" disabled={decide.isPending} onClick={() => decide.mutate("deny")}>
          Deny and escalate
        </button>
      </div>
      {decide.isError && <p className="small err">That did not go through. It may already be decided.</p>}
    </div>
  );
}
