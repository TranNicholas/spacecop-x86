"""Collect one evidence receipt. Reads the lab; never starts, stops, or repairs it.

Every section is collected independently, so a failed collection yields a partial
receipt with an explicit {"error": ...} instead of no receipt. H/G/S/D/W
scenario results are not produced here; they belong to scenario runs.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from . import namespaces

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream/spacecop-demo"


def run(*argv, cwd=ROOT):
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"{' '.join(argv)}: {(result.stderr or result.stdout).strip()}")
    return result.stdout.rstrip("\n")


def section(collect):
    try:
        return collect()
    except Exception as exc:  # a failed check must still leave a receipt
        return {"error": str(exc)}


def git_state(cwd):
    return {"commit": run("git", "rev-parse", "HEAD", cwd=cwd), "dirty": bool(run("git", "status", "--porcelain", cwd=cwd))}


def spacecop_source():
    return {
        "fork_commit": run("git", "rev-parse", "HEAD", cwd=UPSTREAM),
        "source_tree": run("git", "write-tree", cwd=UPSTREAM),
        "dirty": bool(run("git", "status", "--porcelain", cwd=UPSTREAM)),
        "submodules": run("git", "submodule", "status", "--recursive", cwd=UPSTREAM).splitlines(),
    }


def declared_images(config):
    """Return the image reference Compose resolved for every service."""
    model = json.loads(config)
    return {
        name: definition["image"]
        for name, definition in sorted(model["services"].items())
        if definition.get("image")
    }


def container_images(resolved_config):
    """Describe the images of existing Compose containers without trusting the image store.

    With Docker's containerd image store, ``docker compose images`` can try to look
    up a container's config digest as an image and fail the whole command.  Container
    inspect still supplies that config digest and Compose's platform-manifest digest.
    Resolve the current tag for the same platform before comparing the latter.
    """
    model = json.loads(resolved_config)
    default_platform = run(
        "docker", "version", "--format", "{{.Server.Os}}/{{.Server.Arch}}",
    )
    container_ids = run("docker", "compose", "ps", "-a", "-q").splitlines()
    if not container_ids:
        return []

    containers = json.loads(run("docker", "inspect", *container_ids))
    local_ids = {}

    def local_image_id(reference, platform):
        if not reference:
            return None
        key = (reference, platform)
        if key not in local_ids:
            value = section(lambda: run(
                "docker", "image", "inspect", "--platform", platform,
                reference, "--format", "{{.Id}}",
            ))
            local_ids[key] = value if isinstance(value, str) else None
        return local_ids[key]

    inventory = []
    for container in containers:
        container_config = container.get("Config") or {}
        labels = container_config.get("Labels") or {}
        service = labels.get("com.docker.compose.service")
        platform = (model.get("services", {}).get(service, {}).get("platform")
                    or default_platform)
        runtime_manifest_id = labels.get("com.docker.compose.image")
        configured_ref = container_config.get("Image")
        configured_local_id = local_image_id(configured_ref, platform)
        inventory.append({
            "service": service,
            "container": container.get("Name", "").removeprefix("/"),
            "container_id": container.get("Id"),
            "state": (container.get("State") or {}).get("Status"),
            "platform": platform,
            "runtime_image_config_id": container.get("Image"),
            "runtime_image_manifest_id": runtime_manifest_id,
            "configured_image": configured_ref,
            "configured_image_manifest_id": configured_local_id,
            "configured_image_matches_runtime": (
                configured_local_id == runtime_manifest_id
                if configured_local_id and runtime_manifest_id else None
            ),
            "provenance_labels": {
                key: value for key, value in sorted(labels.items())
                if key.startswith("lab.") or key.startswith("org.opencontainers.image.")
            },
        })
    return sorted(inventory, key=lambda item: (item["service"] or "", item["container_id"] or ""))


def collect(out):
    out.mkdir(parents=True, exist_ok=True)
    config = section(lambda: run("docker", "compose", "--profile", "health", "config", "--format", "json"))
    receipt = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "lane": "docker",
        "aerospace_kernel_module_loaded": False,
        "source": {"parent": section(lambda: git_state(ROOT)), "spacecop_fork": section(spacecop_source)},
        "compose_sha256": hashlib.sha256(config.encode()).hexdigest() if isinstance(config, str) else config,
        "images": {
            "declared": section(lambda: declared_images(config)),
            "containers": section(lambda: container_images(config)),
        },
        "plugin": section(lambda: [line for line in run("docker", "compose", "logs", "ground-bootstrap").splitlines() if "installed plugin" in line]),
        "namespaces": section(namespaces.check),
        "host": {"kernel": platform.release(), "docker": section(lambda: run("docker", "--version")),
                 "compose": section(lambda: run("docker", "compose", "version", "--short"))},
    }
    receipt["capture"] = section(lambda: run("docker", "compose", "exec", "-T", "capture", "sh", "-c", "ls -l /evidence").splitlines())
    receipt["copied"] = {}
    for service, source, name in (("capture", "/evidence/.", "capture"), ("witness-zeek", "/var/log/zeek/runs/.", "zeek")):
        result = section(lambda: run("docker", "compose", "cp", f"{service}:{source}", str(out / name)))
        files = sorted(str(path.relative_to(out)) for path in (out / name).rglob("*") if path.is_file())
        # An empty copy is recorded, not hidden: a just-restarted Zeek may not have written logs yet.
        receipt["copied"][name] = result if isinstance(result, dict) else {"files": files}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


if __name__ == "__main__":
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = ROOT / "evaluation/output" / f"receipt-{stamp}"
    collect(path)
    print(path / "receipt.json")
