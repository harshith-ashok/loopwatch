import type { EdgeSample } from "../lib/types";

interface Props {
  samples: EdgeSample[];
  limit: number;
  windowS?: number;
}

const W = 600;
const H = 180;
const PAD = { l: 36, r: 8, t: 8, b: 20 };

/** 60 s temperature line with a dashed limit line. Over-limit points get a ring, not only color. */
export function TempChart({ samples, limit, windowS = 60 }: Props) {
  if (samples.length === 0) {
    return <p className="text-sm text-muted">No telemetry in the last {windowS} s.</p>;
  }
  const maxT = Math.max(limit + 10, ...samples.map((s) => s.temp_c)) + 2;
  const minT = Math.min(30, ...samples.map((s) => s.temp_c)) - 2;
  const x = (ago: number) => PAD.l + ((windowS - ago) / windowS) * (W - PAD.l - PAD.r);
  const y = (t: number) => PAD.t + (1 - (t - minT) / (maxT - minT)) * (H - PAD.t - PAD.b);
  const points = samples.map((s) => `${x(s.ago_s)},${y(s.temp_c)}`).join(" ");
  const summary = `Temperature over the last ${windowS} seconds, latest ${samples[samples.length - 1].temp_c.toFixed(1)} degrees, limit ${limit}`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary} className="w-full">
      <line x1={PAD.l} x2={W - PAD.r} y1={y(limit)} y2={y(limit)} stroke="var(--crit)" strokeDasharray="5 4" />
      <text x={W - PAD.r} y={y(limit) - 4} textAnchor="end" fontSize="11" fill="var(--crit)">
        limit {limit} °C
      </text>
      <polyline points={points} fill="none" stroke="var(--accent)" strokeWidth="2" />
      {samples.map((s, i) =>
        s.temp_c > limit ? (
          <circle key={i} cx={x(s.ago_s)} cy={y(s.temp_c)} r="3.5" fill="none" stroke="var(--crit)" strokeWidth="1.5" />
        ) : null,
      )}
      <text x={PAD.l - 4} y={y(maxT - 2) + 4} textAnchor="end" fontSize="11" fill="var(--muted)">
        {Math.round(maxT - 2)}
      </text>
      <text x={PAD.l - 4} y={y(minT + 2) + 4} textAnchor="end" fontSize="11" fill="var(--muted)">
        {Math.round(minT + 2)}
      </text>
      <text x={PAD.l} y={H - 4} fontSize="11" fill="var(--muted)">
        −{windowS} s
      </text>
      <text x={W - PAD.r} y={H - 4} textAnchor="end" fontSize="11" fill="var(--muted)">
        now
      </text>
    </svg>
  );
}
