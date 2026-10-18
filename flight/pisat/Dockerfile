# Image: upstream cFS/PiSat flight plus the smallest Linux SITL boundary.
# Build inputs: pinned Debian snapshot, pinned upstream tree, lab adapter files,
# and SIMULATION/BUILDTYPE/ENABLE_ASAN from the resolved Compose graph.
ARG APT_SNAPSHOT=20261005T000000Z
ARG SIMULATION=i686-linux-gnu
ARG BUILDTYPE=debug
ARG ENABLE_ASAN=false

# Build the supplied flight tree. Build tools never enter the runtime stage.
FROM debian:trixie-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f AS build
ARG APT_SNAPSHOT
ARG SIMULATION
ARG TARGETARCH
ARG BUILDTYPE
ARG ENABLE_ASAN
RUN case "$TARGETARCH:$(dpkg --print-architecture):$SIMULATION" in \
        386:i386:i686-linux-gnu|arm:armhf:arm-linux-gnueabihf) ;; \
        *) echo "unsupported flight architecture/profile" >&2; exit 1 ;; \
    esac && \
    rm /etc/apt/sources.list.d/debian.sources && \
    printf 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/%s/ trixie main\ndeb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/%s/ trixie-security main\n' "$APT_SNAPSHOT" "$APT_SNAPSHOT" > /etc/apt/sources.list && \
    apt-get update && \
    apt-get install --no-install-recommends -y build-essential cmake python3 libssl-dev libgpiod-dev && \
    rm -rf /var/lib/apt/lists/*

# Stabilize upstream-generated build metadata; this is not a claim about the Pi.
ENV BUILDDATE=202610130000 HOSTNAME=spacecop-builder USER=builder

# Upstream build inputs. The adjacent Dockerfile.dockerignore is the complete
# allowlist for this context.
COPY upstream/spacecop-demo/Makefile /source/Makefile
COPY upstream/spacecop-demo/apps/ /source/apps/
COPY upstream/spacecop-demo/cfe/ /source/cfe/
COPY upstream/spacecop-demo/libs/ /source/libs/
COPY upstream/spacecop-demo/osal/ /source/osal/
COPY upstream/spacecop-demo/psp/ /source/psp/
COPY upstream/spacecop-demo/sample_defs/ /source/sample_defs/
COPY upstream/spacecop-demo/tools/ /source/tools/
WORKDIR /source

# CMake imports CFLAGS during prep. aerospace.ko cannot load in a container, and
# SpaceCOP exits the whole process if it tries, so this disables only the six
# syscall-monitor rules that need it (fork commit "gate kernel rules in SIL
# flight binary"). Every other rule, including MIRE-16, stays as supplied.
# The supplied elf2cfetbl host tool has a time_t printf warning on armhf.
# Apply the same build flags to both architectures; the warning remains visible.
ENV CFLAGS="-DSPACECOP_SIL_NO_KERNEL_MODULE=1 -Wno-error=format"
# Keep cfe_assert: the supplied startup set fills all 20 OSAL module slots.
RUN export SIMULATION ENABLE_ASAN && \
    make O=/out BUILDTYPE="$BUILDTYPE" prep && \
    make O=/out -j4 && \
    make O=/out install && \
    startup=/out/exe/cpu1/cf/cfe_es_startup.scr && \
    test "$(grep -Ec '^CFE_(LIB|APP),' "$startup")" -eq 20 && \
    test "$(grep -Ec '^CFE_LIB,[[:space:]]*cfe_assert,' "$startup")" -eq 1 && \
    test -f /out/exe/cpu1/cf/cfe_assert.so && \
    test -f /out/exe/cpu1/cf/cfe_testcase.so && \
    test -f /out/exe/cpu1/cf/cfe_test_tbl.tbl && \
    rm -f /out/exe/cpu1/cf/aerospace.ko \
          /out/exe/cpu1/cf/cfe_testcase.so \
          /out/exe/cpu1/cf/cfe_test_tbl.tbl && \
    find /out/exe/cpu1 -type f \( -name core-cpu1 -o -name '*.so' \) \
      -exec strip --strip-debug {} +

# Debian co-packages the required LD_PRELOAD interposer with recording and
# wrapper CLIs. Isolate that package here so only the runtime library is kept.
FROM debian:trixie-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f AS device-preload
ARG APT_SNAPSHOT
RUN rm /etc/apt/sources.list.d/debian.sources && \
    printf 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/%s/ trixie main\ndeb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/%s/ trixie-security main\n' "$APT_SNAPSHOT" "$APT_SNAPSHOT" > /etc/apt/sources.list && \
    apt-get update && \
    apt-get install --no-install-recommends -y umockdev && \
    mkdir -p /preload && \
    find /usr/lib -name libumockdev-preload.so.0.0.0 \
      -exec cp {} /preload/libumockdev-preload.so.0 \; && \
    test -s /preload/libumockdev-preload.so.0 && \
    rm -rf /var/lib/apt/lists/*

# Assemble the runtime: compiled flight artifacts first, then lab-only glue.
FROM debian:trixie-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f AS runtime
ARG APT_SNAPSHOT
ARG SIMULATION
ARG BUILDTYPE
ARG ENABLE_ASAN
LABEL org.opencontainers.image.title="SpaceCOP flight with Linux device simulation" \
      lab.build.apt-snapshot="${APT_SNAPSHOT}" \
      lab.flight.build-profile="${SIMULATION}/${BUILDTYPE}" \
      lab.flight.asan="${ENABLE_ASAN}" \
      lab.flight.rule-profile="sil: aerospace.ko rules disabled: CSNE-17 MIRE-17 SIUU-10 SIUU-12 SIUU-15 SIUU-16"
RUN rm /etc/apt/sources.list.d/debian.sources && \
    printf 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/%s/ trixie main\ndeb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/%s/ trixie-security main\n' "$APT_SNAPSHOT" "$APT_SNAPSHOT" > /etc/apt/sources.list && \
    apt-get update && \
    runtime_packages='python3 libssl3t64 libgpiod3 python3-gi gir1.2-umockdev-1.0 libumockdev0 python3-pil' && \
    if [ "$ENABLE_ASAN" = true ]; then runtime_packages="$runtime_packages libasan8"; fi && \
    apt-get install --no-install-recommends -y $runtime_packages && \
    test -d /usr/lib/python3.13/test && \
    rm -rf /var/lib/apt/lists/* \
           /usr/lib/python3.13/test \
           /usr/share/gcc/python \
           /usr/share/gdb
COPY --from=build /out/exe/cpu1/ /opt/pisat/
COPY --from=device-preload /preload/libumockdev-preload.so.0 /usr/local/lib/spacecop-lab/libumockdev-preload.so.0

# Runtime glue. It creates Linux device facades and supervises only the
# unchanged core-cpu1 executable; configuration is in runtime.json.
COPY flight/pisat/camera.py \
     flight/pisat/device_host.py \
     flight/pisat/i2c.py \
     flight/pisat/lifecycle.py \
     flight/pisat/models.py \
     flight/pisat/supervisor.py \
     /usr/lib/spacecop-lab/flight/pisat/
COPY flight/pisat/runtime.json /etc/spacecop-lab/runtime.json
COPY --chmod=755 flight/pisat/rpicam-still /usr/local/bin/rpicam-still
RUN mkdir -p /var/pisat/data /var/pisat/logs /var/pisat/cti && \
    ln -s /usr/local/bin/rpicam-still /usr/local/bin/raspistill

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/usr/lib/spacecop-lab \
    SIL_RUNTIME_PROFILE=/etc/spacecop-lab/runtime.json
WORKDIR /opt/pisat
ENTRYPOINT ["python3", "-m", "flight.pisat.supervisor"]
