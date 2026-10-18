"""Fail if a namespace-sharing sidecar observes a superseded flight namespace."""

import json
import subprocess
import sys

# service -> namespaces it must share with flight (compose.yaml network_mode / pid).
SHARED = {"ml": ("net", "pid"), "capture": ("net",), "witness-zeek": ("net",)}


def identity(service, kinds):
    out = subprocess.run(
        ["docker", "compose", "exec", "-T", service, "sh", "-c",
         "for k in " + " ".join(kinds) + "; do echo $k=$(readlink /proc/self/ns/$k); done"],
        capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(f"cannot read namespaces of {service}: {out.stderr.strip()}")
    return dict(line.split("=", 1) for line in out.stdout.split())


def check():
    flight = identity("flight", ("net", "pid"))
    report, stale = {"flight": flight}, []
    for service, kinds in SHARED.items():
        seen = identity(service, kinds)
        report[service] = seen
        stale += [f"{service} {kind}" for kind in kinds if seen[kind] != flight[kind]]
    report["stale"] = stale
    return report


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, indent=2))
    if result["stale"]:
        sys.exit("Sidecars observe a superseded flight namespace (run `make recreate-sidecars`): " + ", ".join(result["stale"]))
