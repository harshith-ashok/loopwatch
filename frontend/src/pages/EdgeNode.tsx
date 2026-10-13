import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Kpi } from "../components/Kpi";
import { StatusPill } from "../components/StatusPill";
import { TempChart } from "../components/TempChart";
import { apiGet, apiPost } from "../lib/api";
import type { EdgeStatusView } from "../lib/types";

const fmt = (v: number | null, unit = "", digits = 0) => (v === null ? "–" : `${v.toFixed(digits)}${unit}`);

function uptime(s: number | null): string {
  if (s === null) return "–";
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  return d > 0 ? `${d}d ${h}h` : h > 0 ? `${h}h ${m}m` : `${m}m ${s % 60}s`;
}

export default function EdgeNode() {
  const qc = useQueryClient();
  const { data, isPending, isError } = useQuery({
    queryKey: ["edge", "status"],
    queryFn: () => apiGet<EdgeStatusView>("/edge/status"),
    refetchInterval: 5_000, // SSE edge.telemetry also invalidates this, polling is the safety net
  });

  // Heartbeat age keeps counting between messages.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const inject = useMutation({
    mutationFn: (path: string) => apiPost(path),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["edge"] });
      void qc.invalidateQueries({ queryKey: ["incidents"] });
      void qc.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  if (isPending) return <p className="text-muted">Loading edge node…</p>;
  if (isError || !data) return <p className="text-crit">Could not load the edge node. Is the backend running?</p>;

  const age = data.last_seen ? Math.max(0, (now - new Date(data.last_seen).getTime()) / 1000) : null;
  const hot = data.temp_c !== null && data.temp_c > data.temp_limit_c;
  const btn = "rounded-md border border-border px-3 py-1.5 text-sm hover:bg-surface-2 disabled:opacity-60";

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Edge node</h1>
          <p className="mt-1 font-mono text-sm text-muted">{data.node}</p>
        </div>
        {!data.seen ? (
          <StatusPill status="neutral">Never reported</StatusPill>
        ) : data.online ? (
          <StatusPill status="ok">Online</StatusPill>
        ) : (
          <StatusPill status="crit">Offline</StatusPill>
        )}
      </header>

      <div className="grid grid-cols-2 gap-4 min-[900px]:grid-cols-5">
        <Kpi
          label="Temperature"
          value={fmt(data.temp_c, " °C", 1)}
          hint={hot ? `▲ Above ${data.temp_limit_c} °C limit` : `Limit ${data.temp_limit_c} °C`}
        />
        <Kpi label="Uptime" value={uptime(data.uptime_s)} />
        <Kpi label="Signal" value={fmt(data.rssi_dbm, " dBm")} />
        <Kpi label="Heartbeat age" value={age === null ? "–" : `${age.toFixed(0)} s`} hint="Offline after 3 missed (6 s)" />
        <Kpi label="Fan" value={fmt(data.fan_rpm, " rpm")} hint={data.fan_rpm === 0 ? "✕ Stalled" : undefined} />
      </div>

      <section aria-labelledby="temp-h" className="rounded-lg border border-border bg-surface p-4">
        <h2 id="temp-h" className="mb-2 font-semibold">
          Temperature, last 60 s
        </h2>
        <TempChart samples={data.history} limit={data.temp_limit_c} />
      </section>

      <section aria-labelledby="inject-h" className="rounded-lg border border-border bg-surface p-4">
        <h2 id="inject-h" className="font-semibold">
          Simulated faults
        </h2>
        <p className="mt-1 text-sm text-muted">
          The node is simulated. These switches change what it reports; the system has to notice on its own.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" className={btn} disabled={inject.isPending} onClick={() => inject.mutate("/faults/overheat")}>
            Overheat
          </button>
          <button type="button" className={btn} disabled={inject.isPending} onClick={() => inject.mutate("/faults/link")}>
            Drop link
          </button>
          <button type="button" className={btn} disabled={inject.isPending} onClick={() => inject.mutate("/faults/reset")}>
            Restore
          </button>
        </div>
        {inject.isError && <p className="mt-2 text-sm text-crit">That did not work. Check the backend.</p>}
      </section>

      <section aria-labelledby="payload-h" className="rounded-lg border border-border bg-surface p-4">
        <h2 id="payload-h" className="font-semibold">
          Latest message
        </h2>
        <pre className="mt-2 overflow-x-auto font-mono text-sm text-muted">
          {data.latest ? JSON.stringify(data.latest, null, 2) : "No message received yet."}
        </pre>
      </section>
    </div>
  );
}
