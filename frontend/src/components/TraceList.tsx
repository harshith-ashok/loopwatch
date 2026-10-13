import { useState } from "react";
import { rel, secondsBetween, TOOL_AGENT } from "../lib/format";
import type { EvidenceView } from "../lib/types";
import { Icon } from "./Icon";
import { StatusPill } from "./StatusPill";

function summarise(result: Record<string, unknown>): string {
  const text = JSON.stringify(result);
  return text.length > 220 ? `${text.slice(0, 220)}…` : text;
}

/** Collapsible tool calls. Results are data and rendered as text only. */
export function TraceList({ evidence, openedAt }: { evidence: EvidenceView[]; openedAt: string }) {
  const [open, setOpen] = useState(true);
  if (evidence.length === 0) return <p className="empty">The coordinator is dispatching specialists.</p>;
  const agents = new Set(evidence.map((e) => TOOL_AGENT[e.tool] ?? e.tool)).size;
  return (
    <>
      <button type="button" className={`trace-btn${open ? " open" : ""}`} aria-expanded={open} onClick={() => setOpen(!open)}>
        <Icon name="chev" size={14} />
        {evidence.length} tool calls by {agents} specialists
      </button>
      {open && (
        <ol className="calls">
          {evidence.map((c) => (
            <li key={c.ref}>
              <div className="call-h">
                <span className="chip">{c.ref}</span>
                <StatusPill>{TOOL_AGENT[c.tool] ?? c.tool}</StatusPill>
                <span className="mono t">{rel(secondsBetween(openedAt, c.created_at))}</span>
              </div>
              <code className="call">
                {c.tool}({Object.entries(c.args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})
              </code>
              <p className="muted small">{summarise(c.result)}</p>
            </li>
          ))}
        </ol>
      )}
    </>
  );
}
