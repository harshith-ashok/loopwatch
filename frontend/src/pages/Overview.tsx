import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ApprovalCard } from "../components/ApprovalCard";
import { FaultInjector } from "../components/FaultInjector";
import { JourneyCard } from "../components/JourneyCard";
import { StageSteps } from "../components/StageSteps";
import { Kpi } from "../components/Kpi";
import { StatusPill } from "../components/StatusPill";
import { apiGet } from "../lib/api";
import { TERMINAL_STATES, type AuditEventView, type IncidentView, type OverviewView } from "../lib/types";

export default function Overview() {
  const overview = useQuery({
    queryKey: ["overview"],
    queryFn: () => apiGet<OverviewView>("/overview"),
    refetchInterval: 10_000,
  });
  const audit = useQuery({
    queryKey: ["audit", "feed"],
    queryFn: () => apiGet<AuditEventView[]>("/audit?limit=12"),
  });
  const incidents = useQuery({
    queryKey: ["incidents"],
    queryFn: () => apiGet<IncidentView[]>("/incidents"),
  });

  const data = overview.data;
  const open = (incidents.data ?? []).filter((i) => !TERMINAL_STATES.includes(i.state) && !i.is_demo);
  const awaiting = open.filter((i) => i.pending_action);
  const latest = audit.data?.find((e) => e.incident_id === open[0]?.id);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Overview</h1>
        <p className="mt-1 text-muted">Is the business working right now?</p>
      </header>

      {overview.isError && <p className="text-crit">Could not load the overview. Is the backend running?</p>}

      <div className="grid grid-cols-2 gap-4 min-[900px]:grid-cols-4">
        <Kpi
          label="Journeys healthy"
          value={data ? `${data.journeys_healthy}/${data.journeys_total}` : "–"}
          hint="Latest run passed"
        />
        <Kpi label="Open incidents" value={data ? data.open_incidents : "–"} hint="Not yet closed" />
      </div>

      {awaiting.map((i) => (
        <ApprovalCard key={i.id} incidentId={i.id} action={i.pending_action!} likelyCause={i.top_cause}
          incidentTitle={i.title} />
      ))}

      {open.length > 0 && (
        <section aria-labelledby="open-incidents" className="rounded-lg border border-crit bg-crit-bg p-4">
          <h2 id="open-incidents" className="font-semibold">
            <span aria-hidden="true">✕ </span>Incident in progress
          </h2>
          {open.map((i) => (
            <div key={i.id} className="mt-3 space-y-2">
              <Link to={`/incidents/${i.id}`} className="text-sm font-medium underline">
                #{i.id} {i.title}
              </Link>
              <StageSteps stage={i.stage} state={i.state} />
            </div>
          ))}
          {latest && (
            <p className="mt-3 text-sm text-muted">
              Latest: <span className="text-text">{latest.actor}</span> {latest.action.replaceAll("_", " ")}
            </p>
          )}
        </section>
      )}

      <FaultInjector />

      <section aria-labelledby="journeys-h">
        <h2 id="journeys-h" className="mb-3 font-semibold">
          Journeys
        </h2>
        <div className="grid gap-4 min-[900px]:grid-cols-2">
          {overview.isPending && <p className="text-muted">Loading…</p>}
          {data?.journeys.map((j) => <JourneyCard key={j.id} journey={j} showSteps={false} />)}
        </div>
      </section>

      <section aria-labelledby="feed-h" className="rounded-lg border border-border bg-surface p-4">
        <div className="flex items-center justify-between">
          <h2 id="feed-h" className="font-semibold">
            Live feed
          </h2>
          <StatusPill status="neutral">Audit events</StatusPill>
        </div>
        <ul className="mt-3 space-y-1 font-mono text-sm text-muted">
          {audit.isPending && <li>Loading…</li>}
          {audit.isError && <li className="text-crit">Could not load the feed.</li>}
          {audit.data?.length === 0 && <li>Nothing has happened yet.</li>}
          {audit.data?.map((e) => (
            <li key={e.id}>
              <span>{new Date(e.ts).toLocaleTimeString()}</span> <span className="text-text">{e.actor}</span>{" "}
              {e.action.replaceAll("_", " ")}
              {e.incident_id ? ` (#${e.incident_id})` : ""}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
