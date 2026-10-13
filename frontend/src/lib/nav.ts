import type { IconName } from "../components/Icon";

export const NAV_ITEMS: { to: string; label: string; icon: IconName }[] = [
  { to: "/", label: "Overview", icon: "grid" },
  { to: "/incidents", label: "Incidents", icon: "alert" },
  { to: "/journeys", label: "Journeys", icon: "activity" },
  { to: "/edge", label: "Edge node", icon: "cpu" },
  { to: "/policies", label: "Policies", icon: "shield" },
  { to: "/audit", label: "Audit log", icon: "list" },
  { to: "/scorecard", label: "Scorecard", icon: "bars" },
];
