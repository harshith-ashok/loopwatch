export type Status = "ok" | "warn" | "crit" | "acc" | "";

/** Pill from the reference design. The label always carries the meaning; colour is secondary. */
export function StatusPill({ status = "", dot = false, children }: { status?: Status; dot?: boolean; children: React.ReactNode }) {
  return (
    <span className={`pill ${status}`.trim()}>
      {dot && <i className="dot" />}
      {children}
    </span>
  );
}
