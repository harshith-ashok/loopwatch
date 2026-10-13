import { render, screen } from "@testing-library/react";
import { HypothesisList } from "./HypothesisList";

describe("HypothesisList", () => {
  it("says evidence is being collected while investigating", () => {
    render(<HypothesisList hypotheses={[]} investigating />);
    expect(screen.getByRole("status")).toHaveTextContent(/collecting evidence/);
  });

  it("shows confidence and labelled evidence chips, with the top one selected", () => {
    render(
      <HypothesisList
        hypotheses={[{ rank: 1, cause: "Order worker stalled", cause_key: "worker_stalled", confidence: 0.86, supporting: ["E2"], weakening: ["E5"] }]}
      />,
    );
    expect(screen.getByRole("progressbar", { name: /Order worker stalled/ })).toHaveAttribute("aria-valuenow", "86");
    expect(screen.getByText("E2 supports")).toBeInTheDocument();
    expect(screen.getByText("E5 weakens")).toBeInTheDocument();
    expect(screen.getByText("Selected")).toBeInTheDocument();
  });
});
