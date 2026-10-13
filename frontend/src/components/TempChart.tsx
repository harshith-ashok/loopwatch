import type { EdgeSample } from "../lib/types";

const W = 560;
const H = 170;
const L = 34;
const R = 10;
const T = 10;
const B = 22;
const LO = 20;
const HI = 90;

/** Temperature line with gridlines and a dashed limit, as in the reference. */
export function TempChart({ samples, limit, windowS = 60 }: { samples: EdgeSample[]; limit: number; windowS?: number }) {
  if (samples.length === 0) return <p className="empty">No telemetry in the last {windowS} s.</p>;
  const clamp = (t: number) => Math.min(HI, Math.max(LO, t));
  const y = (t: number) => T + ((HI - clamp(t)) / (HI - LO)) * (H - T - B);
  const x = (ago: number) => L + ((windowS - Math.min(windowS, ago)) / windowS) * (W - L - R);
  const pts = samples.map((s) => `${x(s.ago_s).toFixed(1)},${y(s.temp_c).toFixed(1)}`).join(" ");
  const last = samples[samples.length - 1];
  return (
    <svg className="tchart" viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Temperature over the last ${windowS} seconds, latest ${last.temp_c.toFixed(1)} degrees, limit ${limit}`}>
      {[20, 40, 60, 80].map((t) => (
        <g key={t}>
          <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className="gl" />
          <text x={L - 6} y={y(t) + 4} textAnchor="end">{t}</text>
        </g>
      ))}
      <line x1={L} x2={W - R} y1={y(limit)} y2={y(limit)} className="lim" />
      <text x={L + 6} y={y(limit) - 5} className="limt">limit {limit} °C</text>
      <polyline points={pts} className="ln" />
      <circle cx={x(last.ago_s).toFixed(1)} cy={y(last.temp_c).toFixed(1)} r="3.5" className="dt" />
      <text x={L} y={H - 5}>-{windowS} s</text>
      <text x={W - R} y={H - 5} textAnchor="end">now</text>
    </svg>
  );
}
