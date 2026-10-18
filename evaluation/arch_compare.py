"""Run the same benign command/effect probe in either flight ABI lane.

Run after ``make health`` or ``make qemu-health``. This sends commands and
changes flight counters; output is one JSON record for cross-lane comparison.
"""

import json
import subprocess
import time

from .cosmos_api import CosmosApi


def flight_logs():
    return subprocess.check_output(
        ["docker", "compose", "logs", "--no-log-prefix", "flight"], text=True
    )


def flight_event_count(message):
    return flight_logs().count(message)


def wait_for(read, expected, seconds=12):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = read()
        if value == expected:
            return value
        time.sleep(0.2)
    raise RuntimeError(f"expected {expected!r}, last value {value!r}")


def main():
    api = CosmosApi.from_environment()
    camera_count = lambda: api.call("tlm", "CAMERA", "CAMERA_HK_TLM", "COMMANDCOUNT")
    camera_hk_count = lambda: api.call("get_tlm_cnt", "CAMERA", "CAMERA_HK_TLM")
    ci_event = lambda: flight_event_count("CI: NOOP command.")
    sent = []

    def send(target, command, stream_id=None, record=True):
        args = [target, command]
        if stream_id is not None:
            args.append({"CCSDS_STREAMID": stream_id})
        previous = api.call("get_cmd_buffer", target, command)
        previous_count = int(previous["received_count"]) if previous else 0
        api.call("cmd", *args)
        packet = None
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            packet = api.call("get_cmd_buffer", target, command)
            if packet and int(packet["received_count"]) > previous_count:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError(f"no fresh COSMOS command buffer for {target} {command}")
        raw = bytes(packet["buffer"]["raw"])
        if record:
            sent.append({"command": f"{target} {command}", "stream_id": raw[:2].hex(),
                         "bytes": raw.hex()})
        return raw

    if api.call("get_interface", "PISAT_INT")["state"] != "CONNECTED":
        raise RuntimeError("PISAT_INT is not connected")
    wait_for(lambda: isinstance(camera_count(), int), True)
    before = camera_count()
    send("CAMERA", "NOOP")
    wait_for(camera_count, (before + 1) % 256)

    send("CAMERA", "RESET_CTRS")
    time.sleep(1.2)
    stock_reset_count = camera_count()
    send("CAMERA", "RESET_CTRS", 0x19DA)
    wait_for(camera_count, 0)
    corrected_reset_count = camera_count()

    hk_deltas = {}
    for name, stream_id in (("stock", 0x19BB), ("corrected", 0x19DB)):
        hk_before = camera_hk_count()
        for index in range(5):
            send("CAMERA", "CAMERA_REQUEST_HK_CC", stream_id, record=index == 0)
        time.sleep(3)
        hk_deltas[name] = camera_hk_count() - hk_before

    ci_before = ci_event()
    send("CI_LAB", "CI_DEBUG_NOOP_CC")
    time.sleep(1.0)
    stock_ci_events = ci_event() - ci_before
    replay_log_before = flight_logs()
    first = send("CI_LAB", "CI_DEBUG_NOOP_CC", 0x1884)
    wait_for(ci_event, ci_before + 1)
    time.sleep(1.0)
    second = send("CI_LAB", "CI_DEBUG_NOOP_CC", 0x1884)
    wait_for(ci_event, ci_before + 2)
    replay_hex = first.hex().upper()
    replay_event = f"REPLAY_ATTACK:HEX={replay_hex}"
    replay = False
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        current_log = flight_logs()
        fresh_log = (current_log[len(replay_log_before):]
                     if current_log.startswith(replay_log_before) else current_log)
        replay = replay_event in fresh_log
        if replay:
            break
        time.sleep(0.3)

    result = {
        "sent": sent,
        "camera": {"noop_count": (before + 1) % 256,
                   "stock_reset_count": stock_reset_count,
                   "corrected_reset_count": corrected_reset_count,
                   "stock_hk_packets_after_five_requests": hk_deltas["stock"],
                   "corrected_hk_packets_after_five_requests": hk_deltas["corrected"]},
        "ci_lab": {"stock_noop_events": stock_ci_events,
                   "corrected_noop_events": ci_event() - ci_before,
                   "repeat_bytes_identical": first == second,
                   "replay_alert_for_exact_bytes": replay},
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if (stock_reset_count != (before + 1) % 256
            or hk_deltas["corrected"] < hk_deltas["stock"] + 2
            or stock_ci_events != 0
            or not result["ci_lab"]["repeat_bytes_identical"] or not replay):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
