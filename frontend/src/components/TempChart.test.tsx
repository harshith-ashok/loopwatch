import { render, screen } from "@testing-library/react";
import { TempChart } from "./TempChart";

describe("TempChart", () => {
  it("says so when there is no telemetry", () => {
    render(<TempChart samples={[]} limit={70} />);
    expect(screen.getByText(/No telemetry/)).toBeInTheDocument();
  });

  it("describes the latest reading and labels the limit line", () => {
    render(
      <TempChart
        limit={70}
        samples={[
          { ago_s: 4, temp_c: 66, rssi_dbm: -58, fan_rpm: 0 },
          { ago_s: 0, temp_c: 74.5, rssi_dbm: -58, fan_rpm: 0 },
        ]}
      />,
    );
    expect(screen.getByRole("img")).toHaveAccessibleName(/latest 74\.5 degrees, limit 70/);
    expect(screen.getByText("limit 70 °C")).toBeInTheDocument();
  });
});
