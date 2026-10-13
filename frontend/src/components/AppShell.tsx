import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";
import { useEventSource } from "../hooks/useEventSource";
import { apiGet } from "../lib/api";
import { NAV_ITEMS } from "../lib/nav";
import { TERMINAL_STATES, type IncidentView } from "../lib/types";
import { Icon, Logo } from "./Icon";
import { StatusPill } from "./StatusPill";
import { useToast } from "./toast-context";

export function AppShell() {
  const toast = useToast();
  const connection = useEventSource((e) => {
    if (e.type === "incident.opened") {
      toast({ title: `Incident ${String(e.data.id)} opened`, body: String(e.data.title ?? ""), to: `/incidents/${String(e.data.id)}`, tone: "crit" });
    } else if (e.type === "approval.requested") {
      toast({ title: "Approval needed", body: String(e.data.type ?? ""), to: `/incidents/${String(e.data.incident_id)}`, tone: "warn" });
    }
  });
  const incidents = useQuery({ queryKey: ["incidents"], queryFn: () => apiGet<IncidentView[]>("/incidents") });
  const open = (incidents.data ?? []).filter((i) => !TERMINAL_STATES.includes(i.state) && !i.is_demo).length;

  return (
    <div className="app">
      <aside className="rail">
        <div className="brand">
          <Logo />
          <span>Loopwatch</span>
        </div>
        <nav className="nav" aria-label="Pages">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === "/"} className={({ isActive }) => (isActive ? "on" : "")}>
              <Icon name={item.icon} />
              <span>{item.label}</span>
              {item.to === "/incidents" && open > 0 && <span className="count">{open}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="rail-foot">
          {connection === "open" ? (
            <StatusPill status="ok" dot>Live</StatusPill>
          ) : connection === "connecting" ? (
            <StatusPill status="warn" dot>Connecting</StatusPill>
          ) : (
            <StatusPill status="crit" dot>Offline</StatusPill>
          )}
          <p className="hint">Journeys, the shop and the edge node are simulated; the detector, agents and policy are real.</p>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
