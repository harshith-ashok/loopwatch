import { render, screen } from "@testing-library/react";
import { StatusPill } from "./StatusPill";

describe("StatusPill", () => {
  it("renders its label alongside a glyph so color is not the only signal", () => {
    render(<StatusPill status="crit">Down</StatusPill>);
    const pill = screen.getByText("Down").closest("span")!;
    expect(pill).toHaveTextContent("✕");
    expect(pill).toHaveTextContent("Down");
  });
});
