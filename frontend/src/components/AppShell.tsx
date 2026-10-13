import { NavLink, Outlet } from "react-router-dom";
import { useEventSource } from "../hooks/useEventSource";
import { useToast } from "./toast-context";
import { NAV_ITEMS } from "../lib/nav";
import { StatusPill } from "./StatusPill";

const link =
  "block whitespace-nowrap rounded-md px-3 py-2 text-sm text-muted hover:bg-surface-2 hover:text-text aria-[current=page]:bg-surface-2 aria-[current=page]:font-semibold aria-[current=page]:text-text";

export function AppShell() {
  const toast = useToast();
  const connection = useEventSource((e) => {
    if (e.type === "incident.opened") {
      toast({
        title: "Incident opened",
        body: String(e.data.title ?? ""),
        to: `/incidents/${String(e.data.id)}`,
        tone: "crit",
      });
    }
  });
  const pill =
    connection === "open" ? (
      <StatusPill status="ok">Live</StatusPill>
    ) : connection === "connecting" ? (
      <StatusPill status="warn">Connecting</StatusPill>
    ) : (
      <StatusPill status="crit">Offline</StatusPill>
    );

  return (
    <div className="flex h-full flex-col min-[900px]:flex-row">
      <nav
        aria-label="Primary"
        className="flex shrink-0 items-center gap-2 overflow-x-auto border-b border-border bg-surface px-3 py-2 min-[900px]:w-56 min-[900px]:flex-col min-[900px]:items-stretch min-[900px]:gap-1 min-[900px]:border-r min-[900px]:border-b-0 min-[900px]:p-4"
      >
        <div className="flex items-center justify-between gap-3 min-[900px]:mb-4">
          <span className="text-base font-semibold">Loopwatch</span>
          {pill}
        </div>
        <ul className="flex gap-1 min-[900px]:flex-col">
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink to={item.to} end={item.to === "/"} className={link}>
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <main className="min-w-0 flex-1 overflow-y-auto p-4 min-[900px]:p-8">
        <Outlet />
      </main>
    </div>
  );
}
