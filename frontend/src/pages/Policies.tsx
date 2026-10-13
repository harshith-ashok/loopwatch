import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHead } from "../components/PageHead";
import { StatusPill } from "../components/StatusPill";
import { apiGet, apiPut } from "../lib/api";
import { actionName } from "../lib/format";
import { riskTone } from "../lib/incidentState";
import type { PolicyView } from "../lib/types";

const MODES: [string, string][] = [["auto", "Auto"], ["approval", "Needs approval"], ["blocked", "Blocked"]];

export default function Policies() {
  const qc = useQueryClient();
  const { data, isPending, isError } = useQuery({ queryKey: ["policy"], queryFn: () => apiGet<PolicyView>("/policy") });
  const save = useMutation({
    mutationFn: (patch: Record<string, unknown>) => apiPut<PolicyView>("/policy", patch),
    onSuccess: (view) => qc.setQueryData(["policy"], view),
  });

  if (isPending) return <p className="empty">Loading policies…</p>;
  if (isError || !data) return <p className="err" role="alert">Could not load policies. Is the backend running?</p>;

  return (
    <section className="view">
      <PageHead title="Policies" sub="What the agent may do on its own. Changes apply to the next incident and are saved on the server." />
      <div className="card ctrl">
        <label className="switch-row">
          <span><strong>Pause autonomous actions</strong><small>Every action waits for a person, whatever its mode.</small></span>
          <span className="switch">
            <input type="checkbox" checked={data.paused} onChange={(e) => save.mutate({ paused: e.target.checked })} />
            <i />
          </span>
        </label>
        <label className="switch-row">
          <span><strong>Action budget per incident</strong><small>After this many actions the incident escalates.</small></span>
          <input className="num-in mono" type="number" min={1} max={10} value={data.budget}
            onChange={(e) => save.mutate({ budget: Number(e.target.value) })} />
        </label>
        {save.isError && <p className="small err">{(save.error as Error).message}</p>}
      </div>
      <div className="card scroll">
        <table className="tbl">
          <thead><tr><th>Action</th><th>Risk</th><th>Mode</th><th>Rollback plan</th></tr></thead>
          <tbody>
            {data.actions.map((a) => (
              <tr key={a.name}>
                <td><strong>{actionName(a.name)}</strong><div className="muted small mono">{a.name}</div></td>
                <td><StatusPill status={riskTone(a.risk)}>{a.risk}</StatusPill></td>
                <td>
                  <select aria-label={`Mode for ${actionName(a.name)}`} value={a.mode}
                    onChange={(e) => save.mutate({ modes: { [a.name]: e.target.value } })}>
                    {MODES.map(([v, l]) => (
                      <option key={v} value={v} disabled={a.risk === "high" && v === "auto"}>{l}</option>
                    ))}
                  </select>
                  {a.risk === "high" && <div className="muted small">High risk is never automatic.</div>}
                </td>
                <td>{a.rollback}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint">Try it: set "Restart service" to Needs approval, then stall the order queue.</p>
    </section>
  );
}
