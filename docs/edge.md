# Edge node

The edge node is the ESP32 "fulfillment hub". It is both a signal source (temperature, signal
strength, fan speed, heartbeat) and a recovery target (power cycle).

## What is real and what is simulated

| Part | Status |
| --- | --- |
| Backend simulator (`backend/app/edge/simulator.py`) | Real code, used by default. All values are simulated. |
| Telemetry schema, ingest, detection, command queue | Real code, tested. Identical for simulator and board. |
| ESP32 firmware (`firmware/esp32_micropython/`) | OLED dashboard + Wi-Fi telemetry. Sensor values are simulated (random). Not flashed. |
| Physical wiring, real sensors | Not built. |

No result in this project comes from a physical board.

## Message schema

One schema for the simulator, the firmware and `POST /api/v1/edge/telemetry`. Defined in
`backend/app/schemas/edge.py`; sample in `backend/tests/contracts/edge_message.json`.

```json
{ "node": "fulfillment-hub-01", "uptime_s": 518400, "temp_c": 41.2, "rssi_dbm": -58, "fan_rpm": 4200, "fault": null }
```

Out-of-range or malformed messages are rejected with 422 and not stored.

## Heartbeat and commands

- Cadence: every 2 s. Three missed beats (6 s) means offline.
- The reply to every telemetry POST is `{"accepted": true, "commands": [...]}`. Pending device
  commands ride on it. The only command is `power_cycle`. Commands are queued until the node
  next reports, so an offline node gets them when it returns.

## Simulator modes

| Mode | Behaviour | Triggered by |
| --- | --- | --- |
| `normal` | Healthy readings with noise | start, `POST /faults/reset` |
| `overheat` | Fan spins down to 0 RPM, temperature climbs 6 C per tick, capped at 88 C | `POST /faults/overheat` |
| `dropping` | RSSI falls 12 dB per tick; after 3 ticks the node goes offline | `POST /faults/link` |
| `offline` | Sends nothing | end of `dropping` |

A simulated power cycle resets uptime and silences the node for 2 ticks. It does **not** repair
a stalled fan or a lost link, which is what makes the `overheat` scenario end in escalation.

## Detection rules

- `temperature_limit`: above 70 C continuously for 10 s.
- `heartbeat_missed`: no telemetry for 3 intervals.
- The order journey has a "Hub acknowledges" step: slow when the node is above the limit, failed
  (503) when it is offline. With `ack_route=manual` it goes to a manual queue and succeeds.

## Using the firmware (MicroPython, OLED + Wi-Fi)

The sketch is `firmware/esp32_micropython/main.py`: your OLED dashboard plus a Wi-Fi POST every 2 s.

Wiring: SSD1306 128x64 OLED on I2C, SCL = GPIO22, SDA = GPIO21, address 0x3c.

1. Flash a MicroPython build for ESP32 (micropython.org/download).
2. On the board install the display driver: `import mip; mip.install("ssd1306")`.
3. Edit the SETTINGS block at the top of `main.py`: `WIFI_SSID`, `WIFI_PASS`, `BACKEND_URL` (the
   computer's LAN IP, not `localhost`) and `NODE_NAME`. Copy the file to the board as `main.py` with
   `mpremote` or Thonny. It is the only file the board needs besides the `ssd1306` driver.
4. Start the backend so the board can reach it, with the board's node name and the built-in
   simulator off (two senders must not share a name):

   ```bash
   cd backend
   LOOPWATCH_EDGE_NODE=edge-01 LOOPWATCH_EDGE_SIM_ENABLED=false \
     uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
5. Reset the board. The last OLED line shows the network state (`OK`, `HTTP 422`, `backend down`,
   `no wifi`). The Edge page should show the node online with the OLED's values.

Things to know:

- The values are random, in the ranges of the original dashboard. Normal values never cross the
  70 C limit, so no rule fires. Set `SIM_COOLING_FAULT = True` in `main.py` to make the fan stall and
  the temperature climb, which trips `temperature_limit`.
- The Edge page's Overheat and Drop link buttons drive only the backend's own simulator. With that
  simulator off they do not change what the board sends. Unplugging the board, or stopping the
  script, is how you trigger `heartbeat_missed` from real hardware.
- The `fault` field is stored but not used by detection or agents. The string "None" from the old
  dashboard is sent as JSON `null`.
- `uptime_s` counts up from a fixed base instead of being random, so a drop reads as a reboot.
- A `power_cycle` approved in the console is delivered in the reply to the next POST; the board then
  calls `machine.reset()`. The backend's action does not make the board's simulated fan healthy.
- If the OLED or its driver is missing the script prints a message and keeps sending telemetry.

What has been checked: the file compiles, and the message it builds validates against the backend
schema (`backend/tests/test_firmware_message.py`, desktop Python with stubbed modules). What has
not: running on a board, the OLED drawing, Wi-Fi reconnect, `machine.reset()`.

## Replacing a simulated sensor

Each reading is one function in `main.py` with a `TODO(real hardware)` comment: `read_temperature_c`,
`read_fan_rpm`, `read_rssi_dbm` (the real call is `wlan.status("rssi")`). Replace the body; the wire
format is unchanged.
