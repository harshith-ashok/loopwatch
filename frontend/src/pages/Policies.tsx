import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPut } from "../lib/api";
import type { PolicyView } from "../lib/types";

const MODE_LABEL: Record<string, string> = { auto: "Automatic", approval: "Needs approval", blocked: "Blocked" };

export default function Policies() {
  const qc = useQueryClient();
  const { data, isPending, isError } = useQuery({ queryKey: ["policy"], queryFn: () => apiGet<PolicyView>("/policy") });
  const save = useMutation({
    mutationFn: (patch: Record<string, unknown>) => apiPut<PolicyView>("/policy", patch),
    onSuccess: (view) => qc.setQueryData(["policy"], view),
  });

  if (isPending) return <p className="text-muted">Loading policies…</p>;
  if (isError || !data) return <p className="text-crit">Could not load policies. Is the backend running?</p>;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Policies</h1>
        <p className="mt-1 text-muted">What the system may do on its own, and what needs a person.</p>
      </header>

      <section className="space-y-4 rounded-lg border border-border bg-surface p-4" aria-label="Global controls">
        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={data.paused}
            onChange={(e) => save.mutate({ paused: e.target.checked })}
            className="mt-1 h-4 w-4"
          />
          <span>
            <span className="font-medium">Pause automatic actions</span>
            <span className="block text-sm text-muted">
              When on, every action waits for a person to approve it, even low-risk ones.
            </span>
          </span>
        </label>

        <label className="flex flex-wrap items-center gap-3">
          <span className="font-medium">Action budget per incident</span>
          <input
            type="number"
            min={1}
            max={10}
            value={data.budget}
            onChange={(e) => save.mutate({ budget: Number(e.target.value) })}
            className="w-20 rounded-md border border-border bg-surface px-2 py-1"
          />
          <span className="text-sm text-muted">If it runs out, the incident is escalated to a person.</span>
        </label>
        {save.isError && <p className="text-sm text-crit">{(save.error as Error).message}</p>}
      </section>

      <section aria-label="Actions" className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-left text-sm">
          <thead className="bg-surface-2 text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">Action</th>
              <th className="px-3 py-2 font-medium">Risk</th>
              <th className="px-3 py-2 font-medium">Mode</th>
              <th className="px-3 py-2 font-medium">If it goes wrong</th>
            </tr>
          </thead>
          <tbody>
            {data.actions.map((a) => (
              <tr key={a.name} className="border-t border-border align-top">
                <td className="px-3 py-2">
                  <div className="font-mono">{a.name}</div>
                  <div className="text-xs text-muted">{a.targets.join(", ")}</div>
                </td>
                <td className="px-3 py-2">{a.risk}</td>
                <td className="px-3 py-2">
                  <label>
                    <span className="sr-only">Mode for {a.name}</span>
                    <select
                      value={a.mode}
                      onChange={(e) => save.mutate({ modes: { [a.name]: e.target.value } })}
                      className="rounded-md border border-border bg-surface px-2 py-1"
                    >
                      {Object.entries(MODE_LABEL).map(([value, label]) => (
                        <option key={value} value={value} disabled={a.risk === "high" && value === "auto"}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  {a.risk === "high" && <div className="mt-1 text-xs text-muted">High risk is never automatic.</div>}
                </td>
                <td className="px-3 py-2 text-muted">{a.rollback}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
