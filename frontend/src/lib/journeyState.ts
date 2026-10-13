import type { Status } from "../components/StatusPill";
import type { JourneyView } from "./types";

export const journeyTone = (j: JourneyView): Status => (j.status === "ok" ? "ok" : j.status === "failed" ? "crit" : "acc");
export const journeyLabel = (j: JourneyView) =>
  j.status === "ok" ? "Healthy" : j.status === "failed" ? "Failing" : "No runs yet";
