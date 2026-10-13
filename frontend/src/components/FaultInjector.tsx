import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut } from "../lib/api";
import type { PolicyView } from "../lib/types";
import { Icon, type IconName } from "./Icon";
import { useToast } from "./toast-context";

export interface Armed {
  label: string;
  at: number;
  afterIncidentId: number;
}

const SCENARIOS: { key: string; icon: IconName; label: string; sub: string }[] = [
  { key: "stall", icon: "server", label: "Stall the order queue", sub: "Payment captured, order never confirms" },
  { key: "timeout", icon: "zap", label: "Break the checkout API", sub: "Intermittent upstream timeouts" },
  { key: "overheat", icon: "thermo", label: "Overheat the edge node", sub: "Fan stalls, temperature climbs past the limit" },
  { key: "link", icon: "wifi", label: "Drop the edge node's Wi-Fi", sub: "Heartbeats stop, acknowledgements fail" },
];

/** Demo controls. The system has to notice and recover on its own; these only break things. */
export function FaultInjector({ busy = false }: { busy?: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const policy = useQuery({ queryKey: ["policy"], queryFn: () => apiGet<PolicyView>("/policy") });
  const refresh = () => {
    for (const k of ["incidents", "overview", "audit", "edge", "journeys", "score"]) void qc.invalidateQueries({ queryKey: [k] });
  };
  // Respond on the click, not on the server round trip: mark the fault as armed straight away so
  // the console shows it is watching, then confirm when the POST returns.
  const inject = useMutation({
    mutationFn: (v: { path: string; label: string }) => apiPost(v.path),
    onMutate: (v) => {
      const isReset = v.path.endsWith("/reset");
      if (isReset) {
        qc.setQueryData(["armed"], null);
        return;
      }
      const ids = (qc.getQueryData<{ id: number }[]>(["incidents"]) ?? []).map((i) => i.id);
      const armed: Armed = { label: v.label, at: Date.now(), afterIncidentId: Math.max(0, ...ids) };
      qc.setQueryData(["armed"], armed);
      toast({ title: "Fault injected", body: `${v.label}. Watching for it…`, tone: "warn" });
    },
    onError: () => qc.setQueryData(["armed"], null),
    onSuccess: refresh,
  });
  const setPace = useMutation({
    mutationFn: (pace: string) => apiPut<PolicyView>("/policy", { pace }),
    onSuccess: (data) => qc.setQueryData(["policy"], data),
  });
  const disabled = busy;

  return (
    <div className="card">
      <h2 style={{ marginBottom: 12 }}>Fault injector</h2>
      <div className="inj">
        {SCENARIOS.map((s) => (
          <button key={s.key} type="button" className="inj-btn" disabled={disabled} onClick={() => inject.mutate({ path: `/faults/${s.key}`, label: s.label })}>
            <Icon name={s.icon} size={18} />
            <span>
              <strong>{s.label}</strong>
              <small>{s.sub}</small>
            </span>
          </button>
        ))}
      </div>
      <div className="inj-foot">
        <label>
          Pace
          <select value={policy.data?.pace ?? "normal"} disabled={!policy.data} onChange={(e) => setPace.mutate(e.target.value)}>
            {(policy.data?.pace_options ?? ["normal"]).map((p) => (
              <option key={p} value={p}>
                {p[0].toUpperCase() + p.slice(1)}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn" onClick={() => inject.mutate({ path: "/faults/reset", label: "Reset" })}>
          <Icon name="refresh" size={14} />
          Reset system
        </button>
      </div>
      {inject.isError && <p className="small err" style={{ marginTop: 8 }}>That did not work. Check the backend.</p>}
      <p className="hint" style={{ marginTop: 10 }}>
        Faults are injected into the simulated shop and edge node. Pace only changes how long stages pause on screen.
      </p>
    </div>
  );
}
