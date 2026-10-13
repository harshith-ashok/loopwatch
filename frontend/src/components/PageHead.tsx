export function PageHead({ title, sub, right }: { title: string; sub: string; right?: React.ReactNode }) {
  return (
    <header className="head">
      <div>
        <h1>{title}</h1>
        <p className="sub">{sub}</p>
      </div>
      {right}
    </header>
  );
}
