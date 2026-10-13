import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { IncidentDetail } from "../components/IncidentDetail";
import { PageHead } from "../components/PageHead";
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
    <section className="view">
      <PageHead title="Incidents" sub="Evidence, decisions and recovery for every incident." />
      {list.isPending && <p className="empty">Loading incidents…</p>}
      {list.isError && <p className="err" role="alert">Could not load incidents. Is the backend running?</p>}
      {list.data?.length === 0 && <div className="card empty">No incidents. Everything is working.</div>}
      {list.data && list.data.length > 0 && (
        <div className="split">
          <div className="card list" role="list" aria-label="Incident list">
            {list.data.map((i) => (
              <Link key={i.id} to={`/incidents/${i.id}`} role="listitem"
                className={`li${String(i.id) === selectedId ? " on" : ""}`}
                aria-current={String(i.id) === selectedId ? "page" : undefined}>
                <span className="mono muted">#{i.id}</span>
                <strong>{i.title}</strong>
                <span className="pills">
                  <StatusPill status={stateTone(i.state)}>{stateLabel(i.state)}</StatusPill>
                  {i.is_demo && <StatusPill>Sample</StatusPill>}
                </span>
              </Link>
            ))}
          </div>
          {detail.isPending && <div className="card empty">Loading incident…</div>}
          {detail.isError && <div className="card err">Could not load this incident.</div>}
          {detail.data && <IncidentDetail incident={detail.data} />}
        </div>
      )}
    </section>
  );
}
