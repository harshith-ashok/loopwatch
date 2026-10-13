import { useQuery } from "@tanstack/react-query";
import { JourneyCard } from "../components/JourneyCard";
import { PageHead } from "../components/PageHead";
import { apiGet } from "../lib/api";
import type { JourneyView } from "../lib/types";

export default function Journeys() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["journeys"],
    queryFn: () => apiGet<JourneyView[]>("/journeys"),
    refetchInterval: 10_000,
  });
  return (
    <section className="view">
      <PageHead title="Journeys" sub="Synthetic transactions that run every few seconds. A failing step names the service to investigate." />
      {isPending && <p className="empty">Loading journeys…</p>}
      {isError && <p className="err" role="alert">Could not load journeys. Is the backend running?</p>}
      <div className="grid cols-2">{data?.map((j) => <JourneyCard key={j.id} journey={j} />)}</div>
    </section>
  );
}
