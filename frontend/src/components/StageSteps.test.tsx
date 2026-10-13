import { render, screen } from "@testing-library/react";
import { StageSteps } from "./StageSteps";

describe("StageSteps", () => {
  it("marks the current stage and earlier stages as done", () => {
    render(<StageSteps stage="decide" state="awaiting_approval" />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(5);
    expect(items[2]).toHaveAttribute("aria-current", "step");
    expect(items[2]).toHaveTextContent("waiting");
    expect(items[0]).toHaveTextContent("done");
    expect(items[4]).toHaveTextContent("pending");
  });

  it("shows every stage done once an incident is resolved", () => {
    render(<StageSteps stage="verify" state="resolved" />);
    screen.getAllByRole("listitem").forEach((li) => expect(li).toHaveTextContent("done"));
  });
});
