import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApprovalCard } from "../components/ApprovalCard";
import { FaultInjector, type Armed } from "../components/FaultInjector";
import { Kpi } from "../components/Kpi";
import { PageHead } from "../components/PageHead";
import { Sparkline } from "../components/Sparkline";
import { StageSteps } from "../components/StageSteps";
import { StatusPill, type Status } from "../components/StatusPill";
import { apiGet } from "../lib/api";
import { actorTone, describeAudit, hms, JOURNEY_VIA, riskOf, secs } from "../lib/format";
import { riskTone, stateLabel, stateTone } from "../lib/incidentState";
import { journeyLabel, journeyTone } from "../lib/journeyState";
import { TERMINAL_STATES, type AuditEventView, type EdgeStatusView, type IncidentView, type OverviewView, type ScoreView } from "../lib/types";

const KIND: Record<string, string> = { detector: "Alert", agent: "Agent", policy: "Policy", human: "Operator", executor: "Executor", verifier: "Verifier", harness: "Harness" };

export default function Overview() {
  const overview = useQuery({ queryKey: ["overview"], queryFn: () => apiGet<OverviewView>("/overview"), refetchInterval: 10_000 });
  const incidents = useQuery({ queryKey: ["incidents"], queryFn: () => apiGet<IncidentView[]>("/incidents") });
  const audit = useQuery({ queryKey: ["audit", "feed"], queryFn: () => apiGet<AuditEventView[]>("/audit?limit=30") });
  const score = useQuery({ queryKey: ["score"], queryFn: () => apiGet<ScoreView>("/score") });
  const edge = useQuery({ queryKey: ["edge", "status"], queryFn: () => apiGet<EdgeStatusView>("/edge/status"), refetchInterval: 5_000 });

  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const armedQ = useQuery<Armed | null>({ queryKey: ["armed"], queryFn: () => null, staleTime: Infinity, initialData: null });
  const journeys = overview.data?.journeys ?? [];
  const ok = journeys.filter((j) => j.status === "ok").length;
  const bad = journeys.filter((j) => j.status === "failed").length;
  const live = (incidents.data ?? []).find((i) => !i.is_demo);
  const openN = (incidents.data ?? []).filter((i) => !i.is_demo && !TERMINAL_STATES.includes(i.state)).length;
  const awaiting = (incidents.data ?? []).some((i) => i.state === "awaiting_approval");
  const last = live ? (audit.data ?? []).find((e) => e.incident_id === live.id) : undefined;
  const n = edge.data;
  // A fault was just injected and no new incident has opened yet: say so instead of showing nothing.
  const newestId = Math.max(0, ...(incidents.data ?? []).map((i) => i.id));
  const armed = armedQ.data && newestId <= armedQ.data.afterIncidentId && now - armedQ.data.at < 45_000 ? armedQ.data : null;

  const overall: [Status, string] = awaiting ? ["warn", "Waiting for approval"]
    : openN ? ["crit", `${openN} open incident${openN > 1 ? "s" : ""}`]
    : bad ? ["warn", `${bad} journey${bad > 1 ? "s" : ""} failing`]
    : ["ok", "All journeys healthy"];

  return (
    <section className="view">
      <PageHead title="Overview" sub="Journeys, edge telemetry and recovery at a glance."
        right={<StatusPill status={overall[0]} dot>{overall[1]}</StatusPill>} />
      {overview.isError && <p className="err" role="alert">Could not load the overview. Is the backend running?</p>}

      <div className="grid kpis">
        <Kpi label="Journeys healthy" value={overview.data ? ok : "–"} unit={`/${overview.data?.journeys_total ?? 4}`}
          hint={bad ? `${bad} failing` : "Every step passing"} />
        <Kpi label="Open incidents" value={overview.isPending ? "–" : openN} hint={awaiting ? "Waiting for your approval" : "Nothing needs you"} />
        <Kpi label="Mean time to resolve" value={secs(score.data?.metrics.mttr_s?.value)} hint={`${score.data?.metrics.mttr_s?.n ?? 0} resolved incident(s)`} />
        <Kpi label="Edge node" value={n?.online ? `${n.temp_c?.toFixed(1)} °C` : n?.seen ? "Offline" : "–"}
          hint={n?.online ? `Online, ${n.rssi_dbm} dBm` : n?.seen ? `No heartbeat for ${Math.round(n.heartbeat_age_s ?? 0)} s` : "Never reported"} />
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h2 style={{ marginBottom: 12 }}>Journeys</h2>
          {overview.isPending && <p className="empty">Loading journeys…</p>}
          <ul className="rows">
            {journeys.map((j) => (
              <li key={j.id}>
                <div className="nm"><strong>{j.label}</strong><span>{JOURNEY_VIA[j.id] ?? "HTTP probe"}</span></div>
                <StatusPill status={journeyTone(j)}>{journeyLabel(j)}</StatusPill>
                <span className="mono">{j.latest ? `${(j.latest.total_ms / 1000).toFixed(1)} s` : "–"}</span>
                <Sparkline values={j.history_ms} width={110} height={30} tone={j.status === "failed" ? "crit" : "acc"} />
              </li>
            ))}
          </ul>
        </div>

        <div className="stack">
          <div className="card">
            <div className="card-h">
              <h2>{live && TERMINAL_STATES.includes(live.state) ? "Latest incident" : "Incident in progress"}</h2>
              {live && <Link className="link" to={`/incidents/${live.id}`}>Open</Link>}
            </div>
            {armed ? (
              <>
                <p className="inc-t">{armed.label}</p>
                <div className="pills"><StatusPill status="warn" dot>Fault injected, watching</StatusPill></div>
                <ol className="steps" aria-label="Incident stages">
                  <li className="active"><i /><span>Detect</span></li>
                  {["Investigate", "Decide", "Act", "Verify"].map((l) => (<li key={l} className="todo"><i /><span>{l}</span></li>))}
                </ol>
                <p className="now">The journeys are checked every second. The incident appears here as soon as a rule trips.</p>
              </>
            ) : live ? (
              <>
                <p className="inc-t"><span className="mono muted">#{live.id}</span> {live.title}</p>
                <div className="pills">
                  <StatusPill status={riskTone(riskOf(live))}>Risk {riskOf(live)}</StatusPill>
                  <StatusPill status={stateTone(live.state)}>{stateLabel(live.state)}</StatusPill>
                </div>
                <StageSteps stage={live.stage} state={live.state} failedStage={live.failed_stage} />
                {last && <p className="now"><span className="mono">{hms(last.ts)}</span> {describeAudit(last)}</p>}
                {live.pending_action && <ApprovalCard incidentId={live.id} action={live.pending_action} likelyCause={live.top_cause} />}
              </>
            ) : (
              <p className="empty">No incident yet. Use the fault injector to break something.</p>
            )}
          </div>
          <FaultInjector />
        </div>
      </div>

      <div className="card">
        <h2 style={{ marginBottom: 8 }}>Live feed</h2>
        {audit.isError && <p className="err">Could not load the feed.</p>}
        <ul className="feed">
          {audit.data?.length === 0 && <li><span /><span /><span className="empty">Nothing has happened yet.</span></li>}
          {audit.data?.map((e) => (
            <li key={e.id}>
              <span className="mono t">{hms(e.ts)}</span>
              <span className={`tag ${actorTone(e.actor)}`}>{KIND[e.actor] ?? e.actor}</span>
              <span>{describeAudit(e)}{e.is_demo ? " (sample)" : ""}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
