"""Run fast, live diagnostics across the assembled lab."""

import json
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from evaluation import namespaces
from evaluation.cosmos_api import CosmosApi, loopback_url


ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads(Path(__file__).with_name("health_profile.json").read_text())
ONE_SHOT_SERVICES = {"openc3-cosmos-init", "ground-prepare", "ground-bootstrap"}


class Report:
    def __init__(self):
        self.failed = False

    def add(self, name, status, detail):
        self.failed |= status == "FAIL"
        print(f"{status:4}  {name:<24} {detail}", flush=True)

    def attempt(self, name, action):
        try:
            detail = action()
        except Exception as exc:
            self.add(name, "FAIL", str(exc))
            return None
        self.add(name, "PASS", detail)
        return detail

    def skip(self, name, reason):
        self.add(name, "SKIP", reason)


def command(*argv):
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return result.stdout.strip()


def json_rows(text):
    if not text:
        return []
    try:
        value = json.loads(text)
        return value if isinstance(value, list) else [value]
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines()]


def compose_health():
    expected = set(command("docker", "compose", "config", "--services").splitlines())
    deadline = time.monotonic() + PROFILE["startup_timeout_seconds"]
    while True:
        containers = {
            item["Service"]: item
            for item in json_rows(command("docker", "compose", "ps", "-a", "--format", "json"))
        }
        pending = []
        failures = []
        for service in sorted(expected):
            item = containers.get(service)
            if not item:
                pending.append(f"{service}=missing")
                continue
            state = item.get("State", "unknown").lower()
            health = item.get("Health", "").lower()
            status = f"{service}={item.get('Status', state)}"
            if service in ONE_SHOT_SERVICES:
                if state == "exited":
                    if int(item.get("ExitCode", -1)) != 0:
                        failures.append(status)
                else:
                    pending.append(status)
            elif state == "running" and health != "unhealthy":
                continue
            elif state == "exited" or health == "unhealthy":
                failures.append(status)
            else:
                pending.append(status)
        if failures:
            raise RuntimeError("; ".join(failures))
        if not pending:
            return f"{len(expected) - len(ONE_SHOT_SERVICES)} running, 3 setup jobs completed"
        if time.monotonic() >= deadline:
            raise RuntimeError("startup timed out: " + "; ".join(pending))
        time.sleep(1)


def http_json(base, path, payload=None):
    request = Request(
        base + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    try:
        with urlopen(request, timeout=3) as response:
            return json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def elastic_ready(context):
    base = loopback_url("LAB_ELASTIC_PORT")
    status = http_json(base, "/_cluster/health").get("status")
    if status not in {"green", "yellow"}:
        raise RuntimeError(f"cluster status is {status!r}")
    context["elastic"] = base
    return f"{base} cluster={status}"


def kibana_ready():
    base = loopback_url("LAB_KIBANA_PORT")
    deadline = time.monotonic() + PROFILE["startup_timeout_seconds"]
    while True:
        try:
            level = http_json(base, "/api/status").get("status", {}).get("overall", {}).get("level")
            if level == "available":
                return f"{base} status={level}"
            detail = f"status is {level!r}"
        except Exception as exc:
            detail = str(exc)
        if time.monotonic() >= deadline:
            raise RuntimeError(f"{base} not available: {detail}")
        time.sleep(1)


def cosmos_ready(context):
    api = CosmosApi.from_environment()
    api.timeout = 3
    api.authenticate()
    context["cosmos"] = api
    return f"{api.base_url} authenticated"


def interface_ready(api):
    name = PROFILE["interface"]
    last_detail = "not registered"
    deadline = time.monotonic() + PROFILE["startup_timeout_seconds"]
    while time.monotonic() < deadline:
        try:
            if name not in api.call("get_interface_names"):
                last_detail = "not registered"
            else:
                state = api.call("get_interface", name).get("state")
                if state == "CONNECTED":
                    return f"{name} state={state}"
                last_detail = f"state={state!r}"
        except Exception as exc:
            last_detail = str(exc)
        time.sleep(0.5)
    raise RuntimeError(
        f"{name} not connected within {PROFILE['startup_timeout_seconds']}s; {last_detail}"
    )


def namespace_health():
    result = namespaces.check()
    if result["stale"]:
        raise RuntimeError("stale: " + ", ".join(result["stale"]))
    return "ml, capture, and witness share the current flight namespace"


def arm_telemetry(api):
    arming = PROFILE["arming"]
    api.call("cmd", arming["target"], arming["command"],
             {arming["parameter"]: arming["receiver"]})
    return f"destination={arming['receiver']}"


def check_fresh_telemetry(report, api):
    baselines = {}
    for target, packet in PROFILE["telemetry"]:
        try:
            baselines[(target, packet)] = api.call("get_tlm_cnt", target, packet)
        except Exception as exc:
            report.add(f"telemetry {target}", "FAIL", f"cannot read {packet} count: {exc}")

    pending = dict(baselines)
    observed = {}
    last_errors = {}
    deadline = time.monotonic() + PROFILE["timeout_seconds"]
    while pending and time.monotonic() < deadline:
        for key, before in list(pending.items()):
            try:
                count = api.call("get_tlm_cnt", *key)
                if count > before:
                    observed[key] = count
                    del pending[key]
            except Exception as exc:
                last_errors[key] = str(exc)
        if pending:
            time.sleep(0.25)

    for key, before in baselines.items():
        target, packet = key
        if key in observed:
            report.add(f"telemetry {target}", "PASS",
                       f"{packet} count {before} -> {observed[key]}")
        else:
            detail = f"no fresh {packet} within {PROFILE['timeout_seconds']}s"
            if key in last_errors:
                detail += f"; last error: {last_errors[key]}"
            report.add(f"telemetry {target}", "FAIL", detail)


def eps_noop_hits(base):
    query = {
        "size": 100,
        "query": {"bool": {"filter": [
            {"term": {"feed.keyword": "zeek-ccsds"}},
            {"term": {"target.keyword": "EPS"}},
            {"term": {"command_name.keyword": "NOOP"}},
        ]}},
    }
    return http_json(base, "/spacecop-*/_search", query).get("hits", {}).get("hits", [])


def check_round_trip(report, api, elastic):
    spec = PROFILE["round_trip"]
    try:
        # COSMOS retains the last item across flight restarts. Wait for two new
        # packets before using it as the baseline for this boot's counter.
        tlm_count = api.call("get_tlm_cnt", spec["target"], spec["packet"])
        deadline = time.monotonic() + PROFILE["timeout_seconds"]
        while api.call("get_tlm_cnt", spec["target"], spec["packet"]) < tlm_count + 2:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"no two fresh {spec['packet']} packets")
            time.sleep(0.25)
        before = api.call("tlm", spec["target"], spec["packet"], spec["counter"])
        while not isinstance(before, int) and time.monotonic() < deadline:
            time.sleep(0.25)
            before = api.call("tlm", spec["target"], spec["packet"], spec["counter"])
        if not isinstance(before, int):
            raise RuntimeError(f"{spec['counter']} is not available yet: {before!r}")
    except Exception as exc:
        report.add("EPS command round-trip", "FAIL", f"cannot read counter: {exc}")
        report.skip("witness pipeline", "command was not sent")
        return

    witness_ids = None
    if elastic:
        try:
            witness_ids = {hit["_id"] for hit in eps_noop_hits(elastic) if hit.get("_id")}
        except Exception as exc:
            report.add("witness search", "FAIL", str(exc))

    try:
        api.call("cmd", spec["target"], spec["command"])
    except Exception as exc:
        report.add("EPS command round-trip", "FAIL", f"send failed: {exc}")
        report.skip("witness pipeline", "command was not sent")
        return

    expected = (before + spec["delta"]) % spec["modulus"]
    effect = witness = None
    last_effect_error = last_witness_error = None
    deadline = time.monotonic() + PROFILE["timeout_seconds"]
    while time.monotonic() < deadline and (effect is None or (witness_ids is not None and witness is None)):
        if effect is None:
            try:
                if api.call("tlm", spec["target"], spec["packet"], spec["counter"]) == expected:
                    effect = expected
            except Exception as exc:
                last_effect_error = str(exc)
        if witness_ids is not None and witness is None:
            try:
                witness = next(
                    (hit for hit in eps_noop_hits(elastic)
                     if hit.get("_id") and hit["_id"] not in witness_ids),
                    None,
                )
            except Exception as exc:
                last_witness_error = str(exc)
        if effect is None or (witness_ids is not None and witness is None):
            time.sleep(0.25)

    if effect is not None:
        report.add("EPS command round-trip", "PASS", f"CommandCount {before} -> {effect}")
    else:
        detail = f"expected CommandCount {expected} within {PROFILE['timeout_seconds']}s"
        if last_effect_error:
            detail += f"; last error: {last_effect_error}"
        report.add("EPS command round-trip", "FAIL", detail)

    if witness_ids is None:
        report.skip("witness pipeline", "Elasticsearch search unavailable")
    elif witness:
        report.add("witness pipeline", "PASS", f"new Elasticsearch event {witness['_id']}")
    else:
        detail = f"no new EPS NOOP event within {PROFILE['timeout_seconds']}s"
        if last_witness_error:
            detail += f"; last error: {last_witness_error}"
        report.add("witness pipeline", "FAIL", detail)


def main():
    report = Report()
    context = {}
    report.attempt("Compose services", compose_health)
    report.attempt("flight sidecars", namespace_health)
    report.attempt("Elasticsearch HTTP", lambda: elastic_ready(context))
    report.attempt("Kibana HTTP", kibana_ready)
    report.attempt("COSMOS login/API", lambda: cosmos_ready(context))

    api = context.get("cosmos")
    if not api:
        report.skip("PISAT_INT", "COSMOS login/API unavailable")
        report.skip("mission telemetry", "COSMOS login/API unavailable")
        report.skip("EPS command round-trip", "COSMOS login/API unavailable")
        report.skip("witness pipeline", "command was not sent")
    elif report.attempt("PISAT_INT", lambda: interface_ready(api)):
        if report.attempt("telemetry arm", lambda: arm_telemetry(api)):
            check_fresh_telemetry(report, api)
        else:
            report.skip("mission telemetry", "arming failed")
        check_round_trip(report, api, context.get("elastic"))
    else:
        report.skip("mission telemetry", "PISAT_INT is disconnected")
        report.skip("EPS command round-trip", "PISAT_INT is disconnected")
        report.skip("witness pipeline", "command was not sent")

    print("\nHealth check FAILED" if report.failed else "\nHealth check PASSED")
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
