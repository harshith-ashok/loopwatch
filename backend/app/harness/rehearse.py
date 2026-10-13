"""Scripted run of the demo path against a LIVE server, in real time (not accelerated).

    uvicorn app.main:app --port 8000      # in another terminal
    python -m app.harness.rehearse --rounds 3

Per round: reset -> stall (auto, resolved) -> overheat (approval, escalated) -> reset.
Prints wall-clock timings so the 3-minute script can be checked. This is an automated
rehearsal, not a substitute for rehearsing with a person.
"""
import argparse
import sys
import time

import httpx

TERMINAL = {"resolved", "mitigated", "escalated", "false_positive", "cancelled"}


def wait_for(client: httpx.Client, after_id: int, want: set[str], timeout: float) -> tuple[dict | None, float]:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        rows = [i for i in client.get("/api/v1/incidents").json() if i["id"] > after_id and not i["is_demo"]]
        if rows and rows[-1]["state"] in want:
            return rows[-1], time.monotonic() - t0
        time.sleep(0.25)
    return None, time.monotonic() - t0


def last_id(client: httpx.Client) -> int:
    rows = client.get("/api/v1/incidents").json()
    return max((i["id"] for i in rows), default=0)


def round_(client: httpx.Client, n: int) -> dict:
    client.put("/api/v1/policy", json={"paused": False, "pace": "normal", "agent_mode": "loopwatch", "budget": 3})
    t_reset = time.monotonic()
    client.post("/api/v1/faults/reset")
    reset_s = time.monotonic() - t_reset
    time.sleep(3)  # healthy for a moment

    out: dict = {"round": n, "reset_s": round(reset_s, 2)}
    base = last_id(client)
    client.post("/api/v1/faults/stall")
    inc, took = wait_for(client, base, TERMINAL, 60)
    out["stall_state"], out["stall_s"] = (inc or {}).get("state", "TIMEOUT"), round(took, 1)

    client.post("/api/v1/faults/reset")
    time.sleep(3)
    base = last_id(client)
    client.post("/api/v1/faults/overheat")
    inc, took = wait_for(client, base, {"awaiting_approval"}, 90)
    out["overheat_to_approval_s"] = round(took, 1)
    if inc is None:
        out["overheat_state"] = "TIMEOUT"
        return out
    client.post(f"/api/v1/incidents/{inc['id']}/approve", json={"operator": "rehearsal"})
    inc, took2 = wait_for(client, base, TERMINAL, 60)
    out["overheat_state"], out["approval_to_end_s"] = (inc or {}).get("state", "TIMEOUT"), round(took2, 1)
    out["demo_total_s"] = round(out["stall_s"] + 3 + out["overheat_to_approval_s"] + took2, 1)
    client.post("/api/v1/faults/reset")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--rounds", type=int, default=3)
    args = ap.parse_args()
    ok = True
    with httpx.Client(base_url=args.base, timeout=15) as client:
        for n in range(1, args.rounds + 1):
            r = round_(client, n)
            print(r, flush=True)
            ok &= r.get("stall_state") == "resolved" and r.get("overheat_state") == "escalated"
    print("PASS: expected end states in every round" if ok else "FAIL: unexpected end state")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
