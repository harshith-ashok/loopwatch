export function Kpi({
  label,
  value,
  unit,
  hint,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  unit?: string;
  hint?: string;
  tone?: "crit";
}) {
  return (
    <div className="kpi">
      <span className="k">{label}</span>
      <span className={`v mono${tone ? ` ${tone}` : ""}`}>
        {value}
        {unit && <small>{unit}</small>}
      </span>
      {hint && <span className="s">{hint}</span>}
    </div>
  );
}
