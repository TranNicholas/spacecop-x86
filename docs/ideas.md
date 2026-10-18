# Open research checks

These checks need a deployed system or tests beyond the current lab probes. Established lab
behavior is in the [technical reference](technical.md); commands are in the
[operational reference](quick-reference.md). Choose only what bears on a finding.

## `flight/` and the Pi

- **Installed build and state:** Compare the Pi's binaries, libraries, tables, ML assets, and
  loaded `aerospace.ko` with the lab. Record the launcher, privileges, mounts, starting files,
  and reset state. The supplied deployment guide names a systemd unit absent from this checkout.
- **Physical effects:** Check Pico firmware, I²C/UART mapping, camera, and resource samples on a
  Pi/Pico bench before claiming device or alert-rate fidelity. Test timing and recovery when a
  finding depends on bursts, deadlines, or restarts.
- **Kernel-backed rules:** Identify the module actually loaded on the Pi before assessing the six
  disabled Docker rules. The supplied `.ko` may have been rebuilt for HITL.

## `ground/`

- **Station reachability:** Compare exact command bytes and the active station catalog with the
  receiving handler. The supplied plugin's known mismatches are documented; the official
  station's active catalog and audit trail are unavailable here.
- **CFDP retries:** If using the stock upload-request command, repair and test its request
  replay. For direct data/EOF transfer, test loss, interruption, retry, and existing files.
  Confirm any app reload/restoration sequence through the complete cFS path.

## `observer/` and `evaluation/`

- **Research throughput:** Measure input rate and reset reliability before calling the i386 lab
  a scalable fuzzer. Reuse the pinned source in an instrumented harness, then replay reduced and
  sampled negative inputs through COSMOS and Arm QEMU.
- **Alert delivery:** Exercise split/combined ML TCP alerts and partial sends if delivery matters.
  For ground attribution or concealment, compare actual station logs; Zeek and the direct STIX
  reader represent lab evidence only.
