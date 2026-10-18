# Operational reference

Run commands from the repository root. The [README](../README.md) maps the system; the
[technical reference](technical.md) explains why it behaves this way. Docker Compose must support
remote `include` and `!override` (5.4.0 tested). Git must be able to fetch nested submodules.
Local ports and credentials are in [`.env`](../.env).

## Start and stop

| Need | i386 | Arm32 QEMU |
|---|---|---|
| Build and start | `make up` | `make qemu-up` |
| Enable telemetry downlink | `make arm` | `make qemu-arm` |
| Check live path | `make health` | `make qemu-health` |
| Save current evidence | `make evidence` | `make qemu-evidence` |
| Probe command bytes and effects | `make compare` | `make qemu-compare` |
| Stop, retain volumes | `make down` | `make qemu-down` |
| Delete containers **and volumes** | `make clean` | `make qemu-clean` |

`arm` in `make arm` means **enable downlink**, not select an ARM CPU. Downlink starts disabled;
`make health` enables it and sends one benign EPS (power-system) NOOP. `make compare` also sends
commands. `make evidence` only records current state under `evaluation/output/`. On a 15 GiB
host, run one full stack at a time; the first Arm ML build can take tens of minutes. Use i386
for exploration and [replay selected cases in Arm](technical.md#evaluation).

| UI | i386 | Arm32 |
|---|---|---|
| COSMOS | <http://127.0.0.1:2910> | <http://127.0.0.1:2911> |
| Kibana | <http://127.0.0.1:15910> | <http://127.0.0.1:15911> |
| Elasticsearch | <http://127.0.0.1:19910> | <http://127.0.0.1:19911> |

## Send a command and check the result

Open COSMOS, confirm `PISAT_INT` is connected in CmdTlmServer, then use Command Sender and
Telemetry Viewer. The [target definitions](../upstream/spacecop-demo/gsw/openc3-cosmos-cfs/targets/)
list commands and telemetry. Commands reach CI_LAB on UDP **5012**; TO_LAB returns telemetry on
UDP **5013** after downlink is enabled.

| Question | Check |
|---|---|
| Did COSMOS send? | `get_cmd_cnt` / `get_cmd_buffer` through its API; this does not prove execution |
| Did flight act? | New app counter, event, file hash, or state in Telemetry Viewer |
| Did SpaceCOP report? | `SPACECOP_REPORT_TLM.IDS_MSG` or `flight`/`ml` logs; the viewer shows only the latest line |
| What crossed the link? | Packet capture (`pcap`) or Kibana `spacecop-zeek-ccsds-*` |
| Was a security report indexed? | Kibana `spacecop-spacecop-stix-*`; this feed exists only in the lab |
| Which build ran? | `make evidence` receipt and `git submodule status --recursive` |

Logs: `docker compose logs -f flight ml openc3-operator witness-zeek security-logstash`.
Container state: `docker compose ps -a`. Full network/service graph:
`docker compose --profile health config`. Zeek's `valid` means a catalog entry matched; it
does not establish execution or detection.

## Known command catalog corrections

MID is a message ID; FC is the function code within that message. These supplied COSMOS values
differ from the built flight handlers. Override them as shown, then verify a new flight effect.
[Evidence and scope](technical.md#ground) are in the technical reference.

| Command | Catalog MID/FC | Built MID/FC |
|---|---|---|
| CAMERA HK request | `0x19BB/0` | `0x19DB/0` |
| CAMERA reset counters | `0x1DBA/1` | `0x19DA/1` |
| CI_LAB NOOP | `0x18E0/0` | `0x1884/0` |
| CI_LAB reset counters | `0x18E0/2` | `0x1884/1` |
| DS close all | `0x18BB/17` | `0x18BB/18` |
| FM set file permissions | `0x188C/17` | `0x188C/19` |

For FM set file permissions, also set `CCSDS_LENGTH=69` for its 76-byte packet. The CCSDS field
encodes packet bytes after the six-byte primary header, minus one.

COSMOS API example:

```sh
python3 - <<'PY'
from evaluation.cosmos_api import CosmosApi
CosmosApi.from_environment().call(
    "cmd", "CAMERA", "CAMERA_REQUEST_HK_CC", {"CCSDS_STREAMID": 0x19DB}
)
PY
```

For CAMERA API telemetry lookups, use uppercase item names such as `COMMANDCOUNT`.

## When results differ

| Symptom | Check |
|---|---|
| `PISAT_INT` absent | Allow up to 90 seconds after startup; inspect `openc3-operator` and `ground-bootstrap` logs |
| Telemetry stopped | Run `make arm` or `make qemu-arm`, then confirm a fresh item; enable-output clears TO_LAB's suppression latch |
| Command sent, no effect | Compare MID, function code, declared/actual size, and handler; use the catalog table above |
| File upload verified, then failed | The bundled CFDP file-transfer handler can replay an upload request. Direct data/EOF commands worked in both lanes. Check final size/hash, use a fresh or deleted destination, and keep basename ≤19 bytes. [Details](technical.md#ground) |
| ML alert absent | Confirm `ML Bridge initialized`, then inspect `flight`/`ml` logs; [alert transport has limits](technical.md#flight) |
| Capture or ML attached to old flight | Run `make recreate-sidecars` or `make qemu-recreate-sidecars` |
