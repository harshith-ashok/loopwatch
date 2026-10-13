import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut } from "../lib/api";
import type { PolicyView } from "../lib/types";

const SCENARIOS = [
  { key: "stall", label: "Order worker stalls" },
  { key: "timeout", label: "Payment gateway times out" },
  { key: "overheat", label: "Edge node overheats" },
  { key: "link", label: "Edge node loses Wi-Fi" },
] as const;

/** Demo controls. The system must notice and recover on its own; these only break things. */
export function FaultInjector() {
  const qc = useQueryClient();
  const policy = useQuery({ queryKey: ["policy"], queryFn: () => apiGet<PolicyView>("/policy") });
  const refresh = () => {
    for (const k of ["incidents", "overview", "audit", "edge", "journeys"]) void qc.invalidateQueries({ queryKey: [k] });
  };
  const inject = useMutation({ mutationFn: (path: string) => apiPost(path), onSuccess: refresh });
  const setPace = useMutation({
    mutationFn: (pace: string) => apiPut<PolicyView>("/policy", { pace }),
    onSuccess: (data) => qc.setQueryData(["policy"], data),
  });
  const btn = "rounded-md border border-border px-3 py-1.5 text-sm hover:bg-surface-2 disabled:opacity-60";

  return (
    <section aria-labelledby="inject-h" className="rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="inject-h" className="font-semibold">
          Break something
        </h2>
        <label className="flex items-center gap-2 text-sm text-muted">
          Pace
          <select
            value={policy.data?.pace ?? "normal"}
            onChange={(e) => setPace.mutate(e.target.value)}
            disabled={!policy.data}
            className="rounded-md border border-border bg-surface px-2 py-1 text-text"
          >
            {(policy.data?.pace_options ?? ["normal"]).map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {SCENARIOS.map((s) => (
          <button key={s.key} type="button" className={btn} disabled={inject.isPending}
            onClick={() => inject.mutate(`/faults/${s.key}`)}>
            {s.label}
          </button>
        ))}
        <button type="button" className={`${btn} font-medium`} disabled={inject.isPending}
          onClick={() => inject.mutate("/faults/reset")}>
          Reset everything
        </button>
      </div>
      {inject.isError && <p className="mt-2 text-sm text-crit">That did not work. Check the backend.</p>}
      <p className="mt-3 text-xs text-muted">Pace only changes how long stages pause on screen. It does not change results.</p>
    </section>
  );
}
