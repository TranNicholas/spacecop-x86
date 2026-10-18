# Technical reference

SITL means the flight software runs against simulated devices; HITL means a physical Pi/Pico is
in the loop. This file explains what the lab actually builds, how its components connect, and
what a result can establish. Use the [operational reference](quick-reference.md) for commands and
[open ideas](ideas.md) for tests that remain optional.

[`upstream/spacecop-demo/`](../upstream/spacecop-demo/) at `e91fdc9` is the pinned flight, ML,
and COSMOS plugin source. Project-owned `flight/`, `ground/`, `observer/`, and `evaluation/`
assemble it. The root [`compose.yaml`](../compose.yaml) joins their manifests with the pinned
OpenC3 deployment; `docker compose --profile health config` shows the resolved service graph.

## `flight/`

[`flight/compose.yaml`](../flight/compose.yaml) puts `flight` and `ml` on the internal `mission`
network; ML shares flight's network and process namespace. NASA cFS provides the core Flight
Executive (cFE) and its **Software Bus**, which routes messages between apps. OSAL and PSP adapt
cFS to Linux and map flight paths such as `/cf` and `/data` to real directories.

The flight image builds the fork's **top-level `apps/`**, cFE, OSAL, and PSP. The nested gitlinks
under `sample_defs/apps/` record lineage; they are not the built apps. Mission
[`targets.cmake`](../upstream/spacecop-demo/sample_defs/targets.cmake) selects 18 apps and two
libraries. The [startup script](../upstream/spacecop-demo/sample_defs/cpu1_cfe_es_startup.scr)
loads all 20; another app would need a free OSAL module slot. CI_LAB and TO_LAB handle the link;
CFDP transfers files; SpaceCOP detects; EPS, STPYLD, CAMERA, and SYSMON face Pi hardware. Other
apps provide scheduling, files, and housekeeping.

The checked cFE/OSAL source matches NASA v7.0.0. Mission changes affect CI_LAB, TO_LAB, and
SCH; built CFDP comes from [a separate cFS/OpenC3 project](https://github.com/rtinney1/OpenC3_Cosmos_cFS_CFDP)
and has later transfer changes than its nested gitlink. These are source facts, not a claim about
what was installed on a particular Pi.

### Commands, telemetry, and files

The [CI_LAB decoder](../upstream/spacecop-demo/apps/ci_lab/fsw/src/ci_lab_passthru_decode.c)
receives one CCSDS/cFE command per UDP datagram on port **5012**, checks its header and declared
length, then puts it on the Software Bus. The destination app checks its message ID (MID),
function code (FC), and expected size. CI_LAB has a **768-byte buffer** and processes up to
**11 datagrams** per ingest. Both lanes rejected short packets and declared lengths beyond the
received bytes, but accepted trailing bytes. A 769-byte datagram declaring only 8 bytes was
truncated and its NOOP executed; declaring 769 bytes was rejected. The supplied 596-byte CFDP
data command fits. A sent UDP packet alone does not prove flight acted.

[TO_LAB](../upstream/spacecop-demo/apps/to_lab/fsw/src/to_lab_app.c) starts with downlink
disabled. Once enabled, it sends subscribed Software Bus messages to COSMOS on UDP **5013**.
The built enable handler uses FC **2**; an unused alternate source file says 6. A failed `sendto`
suppresses later sends until enable-output clears the latch. `make arm` waits for `PISAT_INT` and
issues that stock enable command.

Flight [CFDP](../upstream/spacecop-demo/apps/cfdp/fsw/src/cfdp_cfdp.c), the file-transfer app,
appends to an existing destination. For retries, choose a fresh path or delete the old file and
verify the **final** size and hash. OSAL permits at most **19 bytes** in a basename. The ground
side is under [`ground/`](#ground).

### SpaceCOP and its ML service

SpaceCOP watches Software Bus messages and Linux state. It sends selected packet bytes to the
Rust ML service on TCP **9111**, receives JSON alerts on **9112**, and reports via telemetry,
events, or STIX (machine-readable security reports). The
[C bridge](../upstream/spacecop-demo/apps/spacecop/src/ml_interface.c) treats each `recv()`
chunk as one complete alert and does not retry a partial send. Split or combined TCP writes can
therefore lose alerts. It handles `REPLAY_ATTACK`, `COMMAND_FLOODING`, and `ML_ANOMALY`, but not
`STATE_DEVIATION`; generic anomalies have telemetry text without a matching STIX mapping.
Check `ML Bridge initialized` before interpreting a missing alert.

The [Rust server](../upstream/spacecop-demo/spacecop_ml/src/server.rs) detects byte-identical
packets repeated within 30 seconds; a changed CCSDS sequence changes that result. It flags
more than 50 commands in 60 seconds per first six packet-hex characters, then cools down for
30 seconds. SC RTS #2 schedules three SC NOOPs, so correlate bytes and time with alerts.

The enabled DISE-1 file-integrity rule scans `/opt/pisat/cf` and `/var/pisat/data`, but not
`/var/pisat/logs`. It [reports changes](../upstream/spacecop-demo/apps/spacecop/src/functions_file_integrity_linux.c)
without blocking the write or application load. An alert and an effect are separate results.

Both Docker lanes disable the six rules requiring the
[supplied `aerospace.ko`](../upstream/spacecop-demo/apps/spacecop/kernel/aerospace.ko):
`CSNE-17`, `MIRE-17`, `SIUU-10`, `SIUU-12`, `SIUU-15`, and `SIUU-16`. That module is ELF32
little-endian ARMv7, built by Raspbian GCC 10.2.1 for kernel `6.1.21-v7+` with module
versioning. It identifies the supplied file, not the module installed on HITL. The
[build guide](../upstream/spacecop-demo/BUILD.md) stages the checked-in module before a rebuild;
a rebuild would need restaging to reach deployment.

### Simulated Pi interfaces

[`supervisor.py`](../flight/pisat/supervisor.py) runs `core-cpu1` and handles processor resets;
[`runtime.json`](../flight/pisat/runtime.json) supplies fixed I²C, serial, temperature, and
camera data. The [device host](../flight/pisat/device_host.py) presents I²C/thermal data through
UMockdev and feeds serial through a pseudoterminal; a [camera shim](../flight/pisat/rpicam-still)
supplies images. GPIO is unavailable. Both lanes inherit host `/proc`, memory, and disk figures.
Docker runs flight as root with writable `mission-data:/var/pisat`, while the supplied deployment
guide advises read-only code and noexec data.

| Interface | Supplied hardware guide | Compiled app and lab facade |
|---|---|---|
| EPS | Four INA219 sensors on I²C bus 1 | Probes four addresses on buses 1 **and 3**; lab models both |
| STPYLD | Pico `OK` line on `/dev/ttyAMA0` | Opens `/dev/serial0`; expects 19 fields beginning `_START_FLAG_OK BME280` |
| CAMERA | Serial JPEG from Pico/ESP32-CAM | Calls `rpicam-still` or `raspistill`; lab has a deterministic shim |
| Radio | Guide sketches a radio ingest path | Active target builds no radio app; `PISAT_INT` uses direct UDP |

The guide and setup script differ on serial configuration; check `/dev/serial0` on the actual
board. The lab's host-sized resources and fixed sensor values produced nominal ML anomalies.
Compare device effects and alert rates against sampled Pi/Pico inputs.

## `ground/`

[`ground/compose.yaml`](../ground/compose.yaml) pins COSMOS **7.2.1** and installs the supplied
PiSat plugin. `ground-bootstrap` points its `PISAT_INT` connection at `flight`;
`openc3-operator` joins the ground and `mission` networks. The
[interface](../upstream/spacecop-demo/gsw/openc3-cosmos-cfs/plugin.txt) sends command packets to
UDP **5012** and receives telemetry from **5013**. The `edge` network publishes the web UIs to
host loopback; the internal `default` network connects COSMOS and Elastic services.

The catalog describes how COSMOS builds a packet; the compiled app decides what it accepts.
A sweep checked **257** supplied commands for default MIDs and field widths. Live probes found
the [six corrections in the quick reference](quick-reference.md#known-command-catalog-corrections):
CAMERA HK and CI_LAB NOOP ran through COSMOS in both lanes; other corrections used COSMOS on
i386 and matching direct UDP bytes on Arm. The sweep did not cover every FC or field byte order.
Some catalog fields use big-endian while handlers read native little-endian values. The official
station's active catalog is unknown.

COSMOS command counts and buffers prove a send, while a new flight counter, event, or state
proves an effect. A catalog match, SpaceCOP alert, and effect answer different questions.

### File uploads

The bundled [CFDP ground service](../upstream/spacecop-demo/gsw/openc3-cosmos-cfs/microservices/CFDP/cfdp.py)
maps `SOURCE` to its send file and `DESTINATION` to the flight path. Its stock FC30 upload-request
workflow replayed a request after an initially verified transfer in both Docker lanes. Flight
then appended to the existing file and the final integrity check failed. The service relies on
latest telemetry without a durable transaction ID; the pinned plugin remains unchanged.

Direct FC31 data commands plus end-of-file (EOF) from COSMOS verified 24-byte files in both
lanes and a 333-byte file on i386, including deletion and re-upload. Data is **ASCII hex**; the tested
procedure sent at most 256 decoded bytes per command. The bundled Script Runner procedure is a
placeholder. An operator-provided procedure completed upload, file readback, app start, proof
retrieval, and route restoration in Arm QEMU. The operator also reports a HITL proof of remote
code execution; a changed upload path raised an alert but did not prevent it. The exact HITL
script and installed plugin version are unknown. These observations support the direct FC31 path;
the stock FC30 replay is a separate issue.

## `observer/`

[`observer/compose.yaml`](../observer/compose.yaml) puts raw packet capture and Zeek, a network
monitor, in flight's network namespace. Zeek sees command/telemetry UDP on `eth0`; it does not
see flight-local ML loopback, though the broader packet capture does. Zeek's `valid` flag means
the packet matched the supplied catalog, not that flight executed it or SpaceCOP detected it.

Logstash reads Zeek logs and SpaceCOP's `stix_log.json` through read-only mounts, then indexes
them in Elasticsearch for Kibana. Reading that STIX file directly is **lab-only**; HITL would
need downlink or file retrieval. Capture, Zeek logs, and host receipts sit outside flight's
writable mounts. The observer is independent evidence instrumentation, not a ground-station
sensor or a second SpaceCOP detector.

## `evaluation/`

[`health_check.py`](../evaluation/health_check.py) checks startup, COSMOS connectivity, fresh
telemetry, an EPS NOOP effect, and observer ingestion. `make health` also checks browser login
and tool rendering; it enables downlink and sends that NOOP. [`receipt.py`](../evaluation/receipt.py) saves
build and runtime evidence under ignored `evaluation/output/` without changing the lab.
[`arch_compare.py`](../evaluation/arch_compare.py) runs the same small command/effect probe in
either lane.

The resolved **19-service** graphs share internal networks, mission ports, ground/observer
images, source, build path, and runtime configuration. Lane-specific settings select the
flight/ML CPU, image names, host ports, and separate volumes. Flight package versions, startup
files, and project configuration match; ML parser data, rules, and models have matching hashes.
Compiled ELF files differ. The binary `hs_mat.tbl` has the same eight decoded entries but
different ABI padding (20-byte i386 versus 24-byte Arm entries); do not copy raw tables between
lanes.

Both lanes passed full health checks. In paired probes, **20 uplink datagrams** had identical
bytes and command effects; the same **21 telemetry MID/length shapes** appeared. Both standalone
ML servers gave the same output for **45 supplied packets**. These are sampled behaviors, not
proof that every malformed input or packet rate is equivalent.

An application binary interface (ABI) controls data layout, calling conventions, and native
code. Both lab flight binaries use 32-bit little-endian ABIs, but these differences matter:

| Property | i386 Docker | Arm32 Docker | Intended Pi/HITL |
|---|---|---|---|
| Flight binary | ELF32 i386, Debian Trixie, GCC 14.2 | ELF32 ARMv7 armhf under QEMU user mode, same build path | Pi Zero 2 W + Pico, Raspberry Pi OS; installed binary unverified |
| Byte order / pointer / `long` | Little-endian / 4 / 4 bytes | Little-endian / 4 / 4 bytes | Check installed build for native-layout work |
| `time_t` / plain `char` | 4 bytes / signed | 8 bytes / unsigned | Depends on deployed userland/toolchain |
| `uint64_t` after `char`: offset / size | 4 / 12 bytes | 8 / 16 bytes | Depends on ABI and packing |
| Kernel and devices | Docker host kernel and device facades | Same, with QEMU scheduling | Pi kernel, Pico/devices, board timing |
| Launch and storage | Container root, writable mission data | Same policy, separate volumes | Actual privileges, mounts, and starting files unknown |

The Pi Zero 2 W CPU can run 64-bit code, but the active
[`cpu1_SYSTEM`](../upstream/spacecop-demo/sample_defs/targets.cmake) selects the
[`arm-linux-gnueabihf` toolchain](../upstream/spacecop-demo/sample_defs/toolchain-arm-linux-gnueabihf.cmake):
the supplied flight build is **32-bit Arm hard-float**. Both lab `core-cpu1` binaries are PIE,
with a non-executable stack and partial RELRO; neither `core-cpu1` nor `spacecop.so` references
the stack protector. The deployed Pi's binaries and protections are unknown. Arm QEMU logged
scheduler skips and Software Bus overflows, so it is not a board-timing model.

| Finding type | Use i386 for | Confirmation needed |
|---|---|---|
| Packet parsing, command/CFDP state, enabled detection logic | Discover and reduce candidates | Replay exact bytes and starting state in Arm; compare effect and on-board report |
| Native code, memory corruption, loader, raw tables | Trace source and find candidates | Start Arm testing early; layout, allocator, instruction set, and payloads differ |
| Scheduling, resources, devices, kernel rules, station audit | Develop a hypothesis | Use Pi/Pico or ground-station evidence for that boundary |

Native i386 removes QEMU instruction translation, but the current **debug, ASan-off** Compose
stack is an integration lab, with no measured fuzzing throughput. COSMOS calls, cFS scheduling,
UDP loss, and observer indexing can limit case rate. A resettable, instrumented harness could
exercise shared parsing code faster; replay reduced inputs through the normal COSMOS/CI_LAB path
in both lanes. Sample negative and boundary cases in Arm too, since i386-only triage misses
Arm-only bugs. Raw UDP injection reaches CI_LAB directly, including packets the supplied COSMOS
catalog may not send.

To translate a finding to HITL, preserve the exact packet, initial files/state, and observed
flight effect. Compare installed `core-cpu1`, app libraries, startup tables, linked libraries,
and ML assets with the lab before relying on source-level similarity. Check execution, SpaceCOP
reporting, and report delivery separately. For native code, compare the Arm loader, memory layout,
and protections. For device, timing, kernel-rule, or station behavior, use the corresponding
hardware or station evidence. QEMU user mode still uses the host kernel for much syscall behavior.
The supplied [hardware guide](../upstream/spacecop-demo/powerboard_setup/HARDWARE_INTERFACE.md)
identifies the Pi/Pico platform; the actual launcher, installed binaries, mounts, and reset state
remain deployment-specific.
