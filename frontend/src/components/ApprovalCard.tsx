import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiPost } from "../lib/api";
import { getOperator, setOperator } from "../lib/operator";
import type { PendingActionView } from "../lib/types";

interface Props {
  incidentId: number;
  action: PendingActionView;
  likelyCause?: string | null;
  incidentTitle?: string;
}

export function ApprovalCard({ incidentId, action, likelyCause, incidentTitle }: Props) {
  const qc = useQueryClient();
  const [operator, setName] = useState(getOperator);
  const decide = useMutation({
    mutationFn: (verb: "approve" | "deny") => apiPost(`/incidents/${incidentId}/${verb}`, { operator }),
    onSuccess: () => {
      setOperator(operator);
      void qc.invalidateQueries({ queryKey: ["incidents"] });
      void qc.invalidateQueries({ queryKey: ["overview"] });
      void qc.invalidateQueries({ queryKey: ["audit"] });
    },
  });
  const btn = "rounded-md border px-3 py-1.5 text-sm font-medium disabled:opacity-60";

  return (
    <section
      aria-label={`Approval needed for incident ${incidentId}`}
      className="rounded-lg border border-warn bg-warn-bg p-4 text-text"
    >
      <h3 className="font-semibold">
        <span aria-hidden="true">⏸ </span>Awaiting your approval
      </h3>
      {incidentTitle && <p className="mt-1 text-sm text-muted">#{incidentId} {incidentTitle}</p>}
      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted">Action</dt>
        <dd className="font-mono">{action.type}</dd>
        <dt className="text-muted">Target</dt>
        <dd className="font-mono">{action.target}</dd>
        <dt className="text-muted">Risk</dt>
        <dd>{action.risk}</dd>
        {likelyCause && (
          <>
            <dt className="text-muted">Likely cause</dt>
            <dd>{likelyCause.replaceAll("_", " ")}</dd>
          </>
        )}
        <dt className="text-muted">Rollback plan</dt>
        <dd>{action.rollback}</dd>
      </dl>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <label className="text-sm">
          <span className="sr-only">Your name</span>
          <input
            value={operator}
            onChange={(e) => setName(e.target.value)}
            className="w-32 rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
            maxLength={64}
          />
        </label>
        <button
          type="button"
          disabled={decide.isPending}
          onClick={() => decide.mutate("approve")}
          className={`${btn} border-ok bg-ok text-bg`}
        >
          Approve
        </button>
        <button
          type="button"
          disabled={decide.isPending}
          onClick={() => decide.mutate("deny")}
          className={`${btn} border-border bg-surface`}
        >
          Deny
        </button>
      </div>
      {decide.isError && <p className="mt-2 text-sm text-crit">That did not go through. It may already be decided.</p>}
    </section>
  );
}
