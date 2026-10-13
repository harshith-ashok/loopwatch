import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "./Toast";
import { useToast } from "./toast-context";

function Trigger() {
  const toast = useToast();
  return (
    <button onClick={() => toast({ title: "Incident opened", body: "x", to: "/incidents/7", tone: "crit" })}>
      fire
    </button>
  );
}

describe("Toast", () => {
  it("renders an incident link inside the router without crashing (regression)", () => {
    render(
      <MemoryRouter>
        <ToastProvider>
          <Trigger />
        </ToastProvider>
      </MemoryRouter>,
    );
    act(() => screen.getByText("fire").click());
    expect(screen.getByRole("link", { name: "Open incident" })).toHaveAttribute("href", "/incidents/7");
  });
});
