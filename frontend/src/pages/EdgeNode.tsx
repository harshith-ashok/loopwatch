import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Icon } from "../components/Icon";
import { Kpi } from "../components/Kpi";
import { PageHead } from "../components/PageHead";
import { StatusPill } from "../components/StatusPill";
import { useToast } from "../components/toast-context";
import { TempChart } from "../components/TempChart";
import { apiGet, apiPost } from "../lib/api";
import { dur } from "../lib/format";
import type { EdgeStatusView } from "../lib/types";

export default function EdgeNode() {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: n, isPending, isError } = useQuery({
    queryKey: ["edge", "status"],
    queryFn: () => apiGet<EdgeStatusView>("/edge/status"),
    refetchInterval: 5_000,
  });
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const inject = useMutation({
    mutationFn: (path: string) => apiPost(path),
    onMutate: (path) => {
      if (!path.endsWith("/reset")) toast({ title: "Fault injected", body: "Watching for it…", tone: "warn" });
    },
    onSuccess: () => {
      for (const k of ["edge", "incidents", "overview"]) void qc.invalidateQueries({ queryKey: [k] });
    },
  });

  if (isPending) return <p className="empty">Loading edge node…</p>;
  if (isError || !n) return <p className="err" role="alert">Could not load the edge node. Is the backend running?</p>;

  const age = n.last_seen ? Math.max(0, (now - new Date(n.last_seen).getTime()) / 1000) : null;
  const hot = n.temp_c !== null && n.temp_c > n.temp_limit_c;
  const payload = n.latest
    ? JSON.stringify(n.latest, null, 2)
    : `// no message received yet`;

  return (
    <section className="view">
      <PageHead title="Edge node"
        sub={`${n.node} reporting temperature, uptime and link quality. Order acknowledgement depends on its heartbeat.`}
        right={n.seen ? <StatusPill status={n.online ? "ok" : "crit"} dot>{n.online ? "Online" : "Offline"}</StatusPill> : <StatusPill dot>Never reported</StatusPill>} />
      <div className="grid kpis">
        <Kpi label="Temperature" value={n.temp_c !== null ? `${n.temp_c.toFixed(1)} °C` : "—"} tone={hot ? "crit" : undefined}
          hint={n.online ? `Limit ${n.temp_limit_c} °C` : "Last known value"} />
        <Kpi label="Uptime" value={dur(n.uptime_s)} hint="Since last reboot" />
        <Kpi label="Signal" value={n.online && n.rssi_dbm !== null ? `${n.rssi_dbm} dBm` : "—"} hint="Wi-Fi RSSI" />
        <Kpi label="Last heartbeat" value={age === null ? "—" : `${age.toFixed(1)} s`} tone={age !== null && age > 5 ? "crit" : undefined}
          hint="Expected every 2 s" />
        <Kpi label="Fan" value={n.online && n.fan_rpm !== null ? `${n.fan_rpm} RPM` : "—"} hint={n.fan_rpm === 0 ? "Stalled" : "Spinning"} />
      </div>
      <div className="grid cols-2">
        <div className="card">
          <h2 style={{ marginBottom: 10 }}>Temperature, last 60 s</h2>
          <TempChart samples={n.history} limit={n.temp_limit_c} />
        </div>
        <div className="card">
          <h2 style={{ marginBottom: 10 }}>Telemetry message</h2>
          <pre className="code">{payload}</pre>
          <p className="muted small" style={{ marginBottom: 12 }}>
            <span className="mono">POST /api/v1/edge/telemetry</span>, every 2 s
          </p>
          <div className="btns">
            <button type="button" className="btn" onClick={() => inject.mutate("/faults/overheat")}>
              <Icon name="thermo" size={14} />Overheat
            </button>
            <button type="button" className="btn" onClick={() => inject.mutate("/faults/link")}>
              <Icon name="wifi" size={14} />Drop link
            </button>
            <button type="button" className="btn" onClick={() => inject.mutate("/faults/reset")}>
              <Icon name="refresh" size={14} />Restore node
            </button>
          </div>
          {inject.isError && <p className="small err" style={{ marginTop: 8 }}>That did not work. Check the backend.</p>}
        </div>
      </div>
    </section>
  );
}
