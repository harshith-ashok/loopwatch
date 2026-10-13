import { render, screen } from "@testing-library/react";
import { StageSteps } from "./StageSteps";

describe("StageSteps", () => {
  it("marks earlier stages done, the current one waiting, and later ones not reached", () => {
    render(<StageSteps stage="decide" state="awaiting_approval" />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(5);
    expect(items[0]).toHaveClass("done");
    expect(items[2]).toHaveClass("wait");
    expect(items[2]).toHaveTextContent("waiting for approval");
    expect(items[4]).toHaveClass("todo");
  });

  it("shows the failed stage for an escalated incident, and everything done once resolved", () => {
    const { unmount } = render(<StageSteps stage="verify" state="escalated" failedStage="verify" />);
    expect(screen.getAllByRole("listitem")[4]).toHaveClass("fail");
    unmount();
    render(<StageSteps stage="verify" state="resolved" />);
    screen.getAllByRole("listitem").forEach((li) => expect(li).toHaveClass("done"));
  });
});
