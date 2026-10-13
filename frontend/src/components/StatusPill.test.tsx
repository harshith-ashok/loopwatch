import { render, screen } from "@testing-library/react";
import { StatusPill } from "./StatusPill";

describe("StatusPill", () => {
  it("always carries its meaning as text and maps the tone to a class", () => {
    render(<StatusPill status="crit" dot>Escalated</StatusPill>);
    const pill = screen.getByText("Escalated");
    expect(pill).toHaveClass("pill", "crit");
    expect(pill.querySelector(".dot")).not.toBeNull();
  });
});
