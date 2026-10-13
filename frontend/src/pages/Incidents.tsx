import { useQuery } from "@tanstack/react-query";
import { NavLink, useParams } from "react-router-dom";
import { IncidentDetail } from "../components/IncidentDetail";
import { StatusPill } from "../components/StatusPill";
import { apiGet } from "../lib/api";
import { stateLabel, stateTone } from "../lib/incidentState";
import type { IncidentDetailView, IncidentView } from "../lib/types";

export default function Incidents() {
  const { id } = useParams();
  const list = useQuery({ queryKey: ["incidents"], queryFn: () => apiGet<IncidentView[]>("/incidents") });
  const selectedId = id ?? (list.data?.[0] ? String(list.data[0].id) : undefined);
  const detail = useQuery({
    queryKey: ["incidents", selectedId],
    queryFn: () => apiGet<IncidentDetailView>(`/incidents/${selectedId}`),
    enabled: selectedId !== undefined,
  });

  return (
    <section>
      <h1 className="text-2xl font-semibold">Incidents</h1>
      {list.isPending && <p className="mt-4 text-muted">Loading incidents…</p>}
      {list.isError && <p className="mt-4 text-crit">Could not load incidents. Is the backend running?</p>}
      {list.data?.length === 0 && <p className="mt-4 text-muted">No incidents. Everything is working.</p>}

      {list.data && list.data.length > 0 && (
        <div className="mt-4 grid gap-6 min-[900px]:grid-cols-[18rem_1fr]">
          <ul className="space-y-2" aria-label="Incident list">
            {list.data.map((i) => (
              <li key={i.id}>
                <NavLink
                  to={`/incidents/${i.id}`}
                  aria-current={String(i.id) === selectedId ? "page" : undefined}
                  className="block rounded-lg border border-border bg-surface p-3 text-sm hover:bg-surface-2 aria-[current=page]:border-accent"
                >
                  <div className="font-medium">
                    #{i.id} {i.title}
                    {i.is_demo && <span className="ml-2 rounded bg-surface-2 px-1.5 py-0.5 text-xs text-muted">sample</span>}
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <StatusPill status={stateTone(i.state)}>{stateLabel(i.state)}</StatusPill>
                    <span className="font-mono text-xs text-muted">
                      {new Date(i.opened_at).toLocaleTimeString()}
                    </span>
                  </div>
                </NavLink>
              </li>
            ))}
          </ul>

          <div className="min-w-0 rounded-lg border border-border bg-surface p-5">
            {detail.isPending && <p className="text-muted">Loading incident…</p>}
            {detail.isError && <p className="text-crit">Could not load this incident.</p>}
            {detail.data && <IncidentDetail incident={detail.data} />}
          </div>
        </div>
      )}
    </section>
  );
}
