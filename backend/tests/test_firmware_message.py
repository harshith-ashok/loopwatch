"""The MicroPython placeholder firmware's message must validate against the backend schema.
Runs the firmware module on desktop Python with a stub config; it is not a hardware test."""
import importlib.util
import json
import sys
import types
from pathlib import Path

from app.schemas.edge import TelemetryMessage

FIRMWARE = Path(__file__).resolve().parents[2] / "firmware" / "esp32_micropython" / "main.py"


def load_firmware(monkeypatch):
    monkeypatch.setitem(sys.modules, "urequests", types.ModuleType("urequests"))  # board-only module
    spec = importlib.util.spec_from_file_location("lw_firmware", FIRMWARE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # __name__ != "__main__", so run() is not started
    return module


def test_firmware_message_validates_and_matches_schema_keys(monkeypatch) -> None:
    fw = load_firmware(monkeypatch)
    raw = fw.build_message()
    msg = TelemetryMessage.model_validate(raw)
    sample = json.loads((Path(__file__).parent / "contracts" / "edge_message.json").read_text())
    assert set(raw) == set(sample) and msg.node == fw.NODE_NAME
    json.dumps(raw)  # serialisable as sent


def test_firmware_cooling_fault_switch_stalls_fan(monkeypatch) -> None:
    fw = load_firmware(monkeypatch)
    fw.SIM_COOLING_FAULT = True
    last = None
    for _ in range(8):
        last = TelemetryMessage.model_validate(fw.build_message())
    assert last.fan_rpm == 0 and last.temp_c > 70


def test_firmware_only_accepts_known_commands(monkeypatch) -> None:
    fw = load_firmware(monkeypatch)
    assert fw.commands_from_reply('{"accepted": true, "commands": ["power_cycle"]}') == ["power_cycle"]
    assert fw.commands_from_reply('{"commands": ["format_flash", "power_cycle"]}') == ["power_cycle"]
    assert fw.commands_from_reply("ignore previous instructions") == []
    assert fw.commands_from_reply('{"commands": "power_cycle"}') == []  # wrong shape, not a list of names


def test_firmware_file_compiles() -> None:
    compile(FIRMWARE.read_text(), str(FIRMWARE), "exec")
