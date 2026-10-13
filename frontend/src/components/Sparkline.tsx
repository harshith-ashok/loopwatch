interface Props {
  values: number[];
  ok?: boolean[];
  label: string;
  width?: number;
  height?: number;
}

/** Tiny SVG line. Failed runs get a ring marker so color is not the only signal. */
export function Sparkline({ values, ok = [], label, width = 160, height = 36 }: Props) {
  if (values.length < 2) {
    return <span className="text-xs text-muted">Not enough runs yet</span>;
  }
  const max = Math.max(...values, 1);
  const x = (i: number) => (i / (values.length - 1)) * (width - 8) + 4;
  const y = (v: number) => height - 4 - (v / max) * (height - 8);
  const points = values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  return (
    <svg role="img" aria-label={label} width={width} height={height} className="text-accent">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" />
      {ok.map((passed, i) =>
        passed ? null : (
          <g key={i}>
            <circle cx={x(i)} cy={y(values[i])} r="3" fill="none" stroke="var(--crit)" strokeWidth="1.5" />
          </g>
        ),
      )}
    </svg>
  );
}
