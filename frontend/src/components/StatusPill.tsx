export type Status = "ok" | "warn" | "crit" | "neutral";

const STYLE: Record<Status, string> = {
  ok: "bg-ok-bg text-ok",
  warn: "bg-warn-bg text-warn",
  crit: "bg-crit-bg text-crit",
  neutral: "bg-surface-2 text-muted",
};

// Color is never the only signal: every pill carries a glyph and a text label.
const GLYPH: Record<Status, string> = { ok: "●", warn: "▲", crit: "✕", neutral: "○" };

export function StatusPill({ status, children }: { status: Status; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${STYLE[status]}`}
    >
      <span aria-hidden="true">{GLYPH[status]}</span>
      {children}
    </span>
  );
}
