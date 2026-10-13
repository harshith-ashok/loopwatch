const ICONS: Record<string, string> = {
  grid: "M3 3h7v7H3z|M14 3h7v7h-7z|M3 14h7v7H3z|M14 14h7v7h-7z",
  alert: "M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z|M12 9v4|M12 17h.01",
  activity: "M22 12h-4l-3 9L9 3l-3 9H2",
  cpu: "M4 4h16v16H4z|M9 9h6v6H9z|M9 1v3|M15 1v3|M9 20v3|M15 20v3|M20 9h3|M20 14h3|M1 9h3|M1 14h3",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  list: "M8 6h13|M8 12h13|M8 18h13|M3 6h.01|M3 12h.01|M3 18h.01",
  bars: "M18 20V10|M12 20V4|M6 20v-6",
  zap: "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
  thermo: "M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z",
  wifi: "M5 12.55a11 11 0 0 1 14.08 0|M1.42 9a16 16 0 0 1 21.16 0|M8.53 16.11a6 6 0 0 1 6.95 0|M12 20h.01",
  server: "M2 4h20v6H2z|M2 14h20v6H2z|M6 7h.01|M6 17h.01",
  lock: "M5 11h14v10H5z|M8 11V7a4 4 0 0 1 8 0v4",
  refresh: "M23 4v6h-6|M1 20v-6h6|M3.5 9a9 9 0 0 1 14.9-3.4L23 10|M1 14l4.6 4.4A9 9 0 0 0 20.5 15",
  chev: "M6 9l6 6 6-6",
};

export type IconName = keyof typeof ICONS;

export function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {(ICONS[name] ?? "").split("|").map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}

export function Logo() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 12a9 9 0 1 1-2.6-6.4" />
      <path d="M21 4v4h-4" />
      <circle cx="12" cy="12" r="2.2" fill="currentColor" stroke="none" />
    </svg>
  );
}
