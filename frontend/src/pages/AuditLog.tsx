import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { apiGet } from "../lib/api";
import type { AuditEventView } from "../lib/types";

const ACTORS = ["detector", "agent", "policy", "human", "executor", "verifier", "harness"] as const;

export default function AuditLog() {
  const [actor, setActor] = useState<string | null>(null);
  const { data, isPending, isError } = useQuery({
    queryKey: ["audit", actor],
    queryFn: () => apiGet<AuditEventView[]>(`/audit?limit=200${actor ? `&actor=${actor}` : ""}`),
  });

  const chip = (active: boolean) =>
    `rounded-full border px-3 py-1 text-sm ${
      active ? "border-accent bg-surface-2 font-semibold" : "border-border text-muted hover:bg-surface-2"
    }`;

  return (
    <section>
      <h1 className="text-2xl font-semibold">Audit log</h1>
      <p className="mt-1 text-muted">Every state change, with who made it.</p>

      <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Filter by actor">
        <button type="button" aria-pressed={actor === null} onClick={() => setActor(null)} className={chip(actor === null)}>
          All
        </button>
        {ACTORS.map((a) => (
          <button key={a} type="button" aria-pressed={actor === a} onClick={() => setActor(a)} className={chip(actor === a)}>
            {a}
          </button>
        ))}
      </div>

      {isPending && <p className="mt-4 text-muted">Loading…</p>}
      {isError && <p className="mt-4 text-crit">Could not load the audit log.</p>}
      {data?.length === 0 && <p className="mt-4 text-muted">No events{actor ? ` from ${actor}` : ""} yet.</p>}

      {data && data.length > 0 && (
        <div className="mt-4 overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-2 text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Time</th>
                <th className="px-3 py-2 font-medium">Actor</th>
                <th className="px-3 py-2 font-medium">Action</th>
                <th className="px-3 py-2 font-medium">Incident</th>
                <th className="px-3 py-2 font-medium">Detail</th>
              </tr>
            </thead>
            <tbody>
              {data.map((e) => (
                <tr key={e.id} className="border-t border-border align-top">
                  <td className="px-3 py-2 font-mono text-xs whitespace-nowrap">{new Date(e.ts).toLocaleTimeString()}</td>
                  <td className="px-3 py-2">{e.actor}</td>
                  <td className="px-3 py-2">{e.action.replaceAll("_", " ")}</td>
                  <td className="px-3 py-2 font-mono">
                    {e.incident_id ? `#${e.incident_id}` : "–"}
                    {e.is_demo && <span className="ml-1 text-xs text-muted">(sample)</span>}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted">{JSON.stringify(e.detail)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
