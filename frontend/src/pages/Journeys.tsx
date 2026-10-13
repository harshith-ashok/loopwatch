import { useQuery } from "@tanstack/react-query";
import { JourneyCard } from "../components/JourneyCard";
import { apiGet } from "../lib/api";
import type { JourneyView } from "../lib/types";

export default function Journeys() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["journeys"],
    queryFn: () => apiGet<JourneyView[]>("/journeys"),
    refetchInterval: 10_000,
  });

  return (
    <section>
      <h1 className="text-2xl font-semibold">Journeys</h1>
      <p className="mt-1 text-muted">Each journey is checked the way a customer would use it.</p>
      {isPending && <p className="mt-6 text-muted">Loading journeys…</p>}
      {isError && <p className="mt-6 text-crit">Could not load journeys. Is the backend running?</p>}
      <div className="mt-6 grid gap-4 min-[900px]:grid-cols-2">
        {data?.map((j) => <JourneyCard key={j.id} journey={j} />)}
      </div>
    </section>
  );
}
