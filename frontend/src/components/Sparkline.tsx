export type Tone = "acc" | "ok" | "warn" | "crit";

/** Area + line + end dot, as in the reference. */
export function Sparkline({
  values,
  width = 120,
  height = 32,
  tone = "acc",
  label,
}: {
  values: number[];
  width?: number;
  height?: number;
  tone?: Tone;
  label?: string;
}) {
  if (values.length < 2) return <span className="muted small">Not enough runs yet</span>;
  const hi = Math.max(...values, 1);
  const pd = 3;
  const pts = values.map((y, i) => [pd + (i * (width - 2 * pd)) / Math.max(values.length - 1, 1), height - pd - (y / hi) * (height - 2 * pd)]);
  const line = pts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const last = pts[pts.length - 1];
  return (
    <svg className={`spark ${tone}`} width={width} height={height} viewBox={`0 0 ${width} ${height}`}
      role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <polygon points={`${pd},${height - 1} ${line} ${last[0].toFixed(1)},${height - 1}`} className="sa" />
      <polyline points={line} className="sl" />
      <circle cx={last[0].toFixed(1)} cy={last[1].toFixed(1)} r="2.6" className="sd" />
    </svg>
  );
}
