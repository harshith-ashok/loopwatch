import sample from "../../../backend/tests/contracts/incident_detail.json";
import type { IncidentDetailView } from "../lib/types";

// Type-level: if the backend sample stops matching the TypeScript type, `npm run typecheck` fails.
const typed: IncidentDetailView = sample;

describe("incident contract", () => {
  it("backend sample payload has every field the UI type declares", () => {
    const fromType: (keyof IncidentDetailView)[] = [
      "id", "title", "journey", "state", "stage", "rule", "signals", "opened_at", "closed_at", "is_demo", "top_cause", "pending_action",
      "timeline", "evidence", "hypotheses", "actions", "verifications",
    ];
    expect(Object.keys(typed).sort()).toEqual([...fromType].sort());
  });
});
