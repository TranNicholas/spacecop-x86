# SpaceCOP SITL lab

This software-in-the-loop (SITL) lab runs the supplied PiSat flight software in Docker with
simulated Raspberry Pi and Pico devices. COSMOS acts as the ground console: it sends **commands**
to flight and receives **telemetry** (status and data) back. The flight software uses NASA's core
Flight System (cFS). SpaceCOP observes it and consults a machine-learning (ML) service. A
separate lab observer records traffic and reports. The lab supports research into these
interfaces and their behavior.

## How the pieces fit

```text
ground/   COSMOS ──commands──▶ flight/ CI_LAB ──▶ cFS apps
ground/   COSMOS ◀─telemetry── flight/ TO_LAB ◀── cFS apps
flight/   cFS apps ──messages + system state──▶ SpaceCOP ↔ ML
observer/ packet capture + Zeek + Elastic ◀── traffic and SpaceCOP reports
```

CI_LAB receives commands; TO_LAB sends telemetry. SpaceCOP is the flight detector; the observer
is independent lab instrumentation. The [technical reference](docs/technical.md) describes the
exact paths and limits.

The default **i386** lane runs natively on an x86_64 host for fast research. The **Arm32** lane
runs under QEMU to check selected findings against the intended flight user-space architecture.
Hardware-dependent findings still need a Pi/Pico or station check.

## Start

With Docker Compose and access to the nested Git submodules:

```sh
make up
```

Use the [operational reference](docs/quick-reference.md) to enable downlink, check the lab, send
commands, collect evidence, and stop it. [`.env`](.env) holds local ports and credentials.

## Find the source of a behavior

| Path | Purpose |
|---|---|
| [flight/](flight/) | Build and run cFS, SpaceCOP, ML, and simulated Pi devices |
| [ground/](ground/) | Install the supplied COSMOS plugin and connect it to flight |
| [observer/](observer/) | Capture packets and display lab evidence in Elastic/Kibana |
| [evaluation/](evaluation/) | Check health, compare i386/Arm behavior, and save receipts |
| [upstream/spacecop-demo/](upstream/spacecop-demo/) | Pinned supplied flight, ML, and COSMOS source |
| [compose.yaml](compose.yaml) | Entry point that joins the component Compose files |

The project-owned directories build, simulate, and observe the pinned source. For implementation
and fidelity limits, read the [technical reference](docs/technical.md). For optional follow-up
tests, see [open ideas](docs/ideas.md).
