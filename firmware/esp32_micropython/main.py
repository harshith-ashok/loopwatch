"""Loopwatch ESP32 edge node (MicroPython): OLED dashboard + Wi-Fi telemetry.

ALL SENSOR VALUES IN THIS FILE ARE SIMULATED (random, as in the original dashboard). Nothing
here reads a real sensor; each reading is its own function with a TODO(real hardware) note.
The wire format is the Loopwatch telemetry schema (backend/app/schemas/edge.py).

Every 2 s it:
  1. builds one telemetry message
  2. shows it on the SSD1306 OLED (I2C, SCL=GPIO22, SDA=GPIO21, addr 0x3c)
  3. POSTs it to <BACKEND_URL>/api/v1/edge/telemetry
  4. reboots if the reply lists the known command "power_cycle"

Single file: edit the SETTINGS block below, copy this file to the board as main.py.
Needs the `ssd1306` driver on the board:  import mip; mip.install("ssd1306")
Do not commit real Wi-Fi credentials; put them in only on the copy you flash.
STATUS: not run on a board. Syntax-checked, and the message it builds is validated against the
backend schema on desktop Python with stubbed modules.
"""
import json
import random
import time

try:
    import urequests as requests  # older MicroPython builds
except ImportError:  # pragma: no cover - newer builds ship `requests`
    import requests

# ---- SETTINGS (edit these) ---------------------------------------------------------------------
WIFI_SSID = "your-wifi"
WIFI_PASS = "your-password"
BACKEND_URL = "http://192.168.1.50:8000"  # the computer running uvicorn (LAN IP, not localhost)
NODE_NAME = "edge-01"  # must match LOOPWATCH_EDGE_NODE on the backend
# ------------------------------------------------------------------------------------------------

SEND_INTERVAL_S = 2
WIFI_RETRY_S = 5
BASE_UPTIME_S = 518400
KNOWN_COMMANDS = ("power_cycle",)

# Fault strings from the original dashboard. "None" is sent as JSON null.
FAULT_OPTIONS = ["None", "None", "None", "Sensor-Err", "Low-Volt"]

# Set True to make the simulated fan stall and the temperature climb past the 70 C limit, so the
# backend's overheat rule can fire from this board. (The backend's Overheat button only drives
# the backend's own simulator, not this board.)
SIM_COOLING_FAULT = False

_state = {"temp": 41.2, "fan": 4200}
_boot_ms = time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.time() * 1000)


# ---- simulated sensors (placeholders) ----------------------------------------------------------

def read_temperature_c():
    # TODO(real hardware): read an external sensor (DS18B20 via onewire, or a thermistor on an ADC).
    if SIM_COOLING_FAULT:
        _state["temp"] = min(88.0, _state["temp"] + 6.0)
    else:
        _state["temp"] = round(random.uniform(38.0, 55.0), 1)
    return round(_state["temp"], 1)


def read_fan_rpm():
    # TODO(real hardware): count tachometer pulses on a Pin interrupt over a 1 s window.
    if SIM_COOLING_FAULT:
        _state["fan"] = max(0, _state["fan"] - 1400)
    else:
        _state["fan"] = random.randint(3500, 4800)
    return int(_state["fan"])


def read_rssi_dbm(wlan=None):
    # TODO(real hardware): return wlan.status("rssi"). Simulated for now.
    return random.randint(-85, -40)


def read_fault():
    choice = random.choice(FAULT_OPTIONS)
    return None if choice == "None" else choice


def uptime_s():
    now = time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.time() * 1000)
    return BASE_UPTIME_S + (now - _boot_ms) // 1000  # monotonic: the backend treats a drop as a reboot


# ---- message and commands ----------------------------------------------------------------------

def build_message(wlan=None):
    """One telemetry message in the shared schema."""
    return {
        "node": NODE_NAME,
        "uptime_s": int(uptime_s()),
        "temp_c": read_temperature_c(),
        "rssi_dbm": read_rssi_dbm(wlan),
        "fan_rpm": read_fan_rpm(),
        "fault": read_fault(),
    }


def commands_from_reply(text):
    """Treat the reply as data: only known command names are accepted, never free text."""
    try:
        commands = json.loads(text).get("commands", [])
    except (ValueError, AttributeError):
        return []
    return [c for c in commands if c in KNOWN_COMMANDS]


# ---- OLED --------------------------------------------------------------------------------------

def init_display():
    """Return the OLED, or None if it is missing, so telemetry keeps flowing without it."""
    try:
        from machine import I2C, Pin
        import ssd1306

        i2c = I2C(0, scl=Pin(22), sda=Pin(21))
        return ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
    except Exception as e:  # noqa: BLE001 - no display is not fatal
        print("OLED not available:", e)
        return None


def show(oled, msg, net):
    if oled is None:
        return
    oled.fill(0)
    oled.text("Node: {}".format(msg["node"]), 0, 0)
    oled.text("Uptime: {}s".format(msg["uptime_s"]), 0, 10)
    oled.text("Temp: {} C".format(msg["temp_c"]), 0, 20)
    oled.text("RSSI: {} dBm".format(msg["rssi_dbm"]), 0, 30)
    oled.text("Fan: {} RPM".format(msg["fan_rpm"]), 0, 40)
    oled.text("Fault: {}".format(msg["fault"] or "None"), 0, 50)
    oled.text("Net: {}".format(net), 0, 56)
    oled.show()


# ---- networking --------------------------------------------------------------------------------

def connect_wifi(wlan, timeout_s=10):
    if wlan.isconnected():
        return True
    wlan.connect(WIFI_SSID, WIFI_PASS)
    start = time.time()
    while not wlan.isconnected() and time.time() - start < timeout_s:
        time.sleep(0.25)
    return wlan.isconnected()


def send(message):
    """POST one message. Returns (http_status, commands queued for this node)."""
    url = BACKEND_URL + "/api/v1/edge/telemetry"
    response = requests.post(url, data=json.dumps(message), headers={"Content-Type": "application/json"})
    try:
        if response.status_code != 200:
            return response.status_code, []
        return 200, commands_from_reply(response.text)
    finally:
        response.close()


def run():
    import machine
    import network

    oled = init_display()
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    last_try = 0
    net = "connecting"
    print("Edge node {} starting. Ctrl+C to stop.".format(NODE_NAME))
    try:
        while True:
            if not wlan.isconnected() and time.time() - last_try >= WIFI_RETRY_S:
                last_try = time.time()
                net = "wifi..." if not connect_wifi(wlan) else "wifi ok"
            msg = build_message(wlan)
            if wlan.isconnected():
                try:
                    status, commands = send(msg)
                    net = "OK" if status == 200 else "HTTP {}".format(status)
                    if "power_cycle" in commands:
                        show(oled, msg, "rebooting")
                        time.sleep(0.5)
                        machine.reset()
                except OSError:
                    net = "backend down"  # keep looping; it may come back
            else:
                net = "no wifi"
            show(oled, msg, net)
            time.sleep(SEND_INTERVAL_S)
    except KeyboardInterrupt:
        if oled is not None:
            oled.fill(0)
            oled.show()
        print("Edge node stopped.")


if __name__ == "__main__":
    run()
