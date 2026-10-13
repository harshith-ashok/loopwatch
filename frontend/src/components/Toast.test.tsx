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
  it("renders inside the router and navigates without crashing (regression)", () => {
    render(
      <MemoryRouter>
        <ToastProvider>
          <Trigger />
        </ToastProvider>
      </MemoryRouter>,
    );
    act(() => screen.getByText("fire").click());
    expect(screen.getByRole("button", { name: /Incident opened/ })).toBeInTheDocument();
  });
});
