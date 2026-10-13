export function PageStub({ title, blurb }: { title: string; blurb: string }) {
  return (
    <section>
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="mt-2 max-w-prose text-muted">{blurb}</p>
    </section>
  );
}
