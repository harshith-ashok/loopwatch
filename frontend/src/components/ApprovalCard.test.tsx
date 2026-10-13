import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { ApprovalCard } from "./ApprovalCard";

describe("ApprovalCard", () => {
  it("shows the action, risk and rollback plan, and posts the decision with the operator name", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ApprovalCard
          incidentId={7}
          likelyCause="cooling_fault"
          action={{ id: 1, type: "power_cycle_device", target: "fulfillment-hub-01", risk: "high", rollback: "Restore the previous profile" }}
        />
      </QueryClientProvider>,
    );
    expect(screen.getByText("power_cycle_device")).toBeInTheDocument();
    expect(screen.getByText("Restore the previous profile")).toBeInTheDocument();
    expect(screen.getByText("cooling fault")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Approve" }));
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/incidents/7/approve");
    expect(JSON.parse(init.body as string)).toEqual({ operator: "operator" });
    vi.unstubAllGlobals();
  });
});
