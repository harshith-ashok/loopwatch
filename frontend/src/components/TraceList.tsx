import type { EvidenceView } from "../lib/types";

/** Collapsible tool calls. Results are data and rendered as text only. */
export function TraceList({ evidence }: { evidence: EvidenceView[] }) {
  if (evidence.length === 0) return <p className="text-sm text-muted">No tool calls yet.</p>;
  return (
    <ul className="space-y-2">
      {evidence.map((e) => (
        <li key={e.ref}>
          <details className="rounded-md border border-border bg-surface-2 px-3 py-2">
            <summary className="cursor-pointer text-sm">
              <span className="mr-2 rounded bg-surface px-1.5 py-0.5 font-mono text-xs">{e.ref}</span>
              <span className="font-mono">{e.tool}</span>
            </summary>
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap font-mono text-xs text-muted">
              {JSON.stringify({ args: e.args, result: e.result }, null, 2)}
            </pre>
          </details>
        </li>
      ))}
    </ul>
  );
}
