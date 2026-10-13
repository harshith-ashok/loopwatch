import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHead } from "../components/PageHead";
import { StatusPill } from "../components/StatusPill";
import { apiGet } from "../lib/api";
import { describeAudit, fmtTs } from "../lib/format";
import type { AuditEventView } from "../lib/types";

const ACTORS = ["all", "detector", "agent", "policy", "human", "executor", "verifier", "harness"];

export default function AuditLog() {
  const [actor, setActor] = useState("all");
  const { data, isPending, isError } = useQuery({
    queryKey: ["audit", actor],
    queryFn: () => apiGet<AuditEventView[]>(`/audit?limit=200${actor === "all" ? "" : `&actor=${actor}`}`),
  });

  return (
    <section className="view">
      <PageHead title="Audit log" sub="Every detection, decision, approval and action, with who did it." />
      <div className="pills filters" role="group" aria-label="Filter by actor">
        {ACTORS.map((f) => (
          <button key={f} type="button" aria-pressed={actor === f} className={`pill${actor === f ? " acc" : ""}`} onClick={() => setActor(f)}>
            {f}
          </button>
        ))}
      </div>
      {isPending && <p className="empty">Loading…</p>}
      {isError && <p className="err" role="alert">Could not load the audit log.</p>}
      {data && (
        <div className="card scroll">
          <table className="tbl">
            <thead><tr><th>Time</th><th>Actor</th><th>Incident</th><th>Event</th></tr></thead>
            <tbody>
              {data.length === 0 && <tr><td colSpan={4} className="empty">No entries{actor !== "all" ? ` from ${actor}` : ""}.</td></tr>}
              {data.map((e) => (
                <tr key={e.id}>
                  <td className="mono nowrap">{fmtTs(e.ts)}</td>
                  <td><StatusPill>{e.actor}</StatusPill></td>
                  <td>{e.incident_id ? <Link className="link mono" to={`/incidents/${e.incident_id}`}>#{e.incident_id}</Link> : ""}</td>
                  <td>{describeAudit(e)} {e.is_demo && <StatusPill>Sample</StatusPill>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
