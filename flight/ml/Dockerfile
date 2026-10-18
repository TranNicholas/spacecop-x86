# Image: supplied SpaceCOP ML server, parser database, and trained models.
# Build inputs: one Debian snapshot, pinned Rust/base images, upstream Rust
# sources/models, and the same COSMOS target definitions used by the ground.
ARG APT_SNAPSHOT=20261005T000000Z

# Generate the parser database from the supplied command/telemetry catalog.
FROM debian:trixie-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f AS database
ARG APT_SNAPSHOT
RUN rm /etc/apt/sources.list.d/debian.sources && \
    printf 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/%s/ trixie main\ndeb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/%s/ trixie-security main\n' "$APT_SNAPSHOT" "$APT_SNAPSHOT" > /etc/apt/sources.list && \
    apt-get update && apt-get install --no-install-recommends -y python3 python3-flask-sqlalchemy && \
    rm -rf /var/lib/apt/lists/*
COPY upstream/spacecop-demo/spacecop_ml/scripts/ /ml/scripts/
COPY upstream/spacecop-demo/gsw/openc3-cosmos-cfs/targets/ /targets/
COPY upstream/spacecop-demo/spacecop_ml/scml_models/ /runtime-models/
RUN python3 /ml/scripts/build_database.py /targets && \
    find /runtime-models -type f \
      ! -name anomaly_detector.onnx \
      ! -name metadata.json \
      ! -name scaler.json \
      ! -name exact_match_rules.json -delete && \
    find /runtime-models -depth -type d -empty -delete && \
    python3 -c "import sqlite3; c=sqlite3.connect('/ml/instance/cmd_tlm.sqlite'); assert c.execute('select count(*) from telemetry_packets').fetchone()[0]>0"

# Compile the supplied Rust library behind a runtime-only server entry point.
FROM rust:1.85.1-slim-bookworm@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS compiler
ARG APT_SNAPSHOT
RUN rm -f /etc/apt/sources.list.d/debian.sources && \
    printf 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/%s/ bookworm main\ndeb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/%s/ bookworm-security main\n' "$APT_SNAPSHOT" "$APT_SNAPSHOT" > /etc/apt/sources.list && \
    apt-get update && apt-get install --no-install-recommends -y gcc g++ libc6-dev && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /ml
COPY upstream/spacecop-demo/spacecop_ml/Cargo.toml upstream/spacecop-demo/spacecop_ml/Cargo.lock ./
COPY upstream/spacecop-demo/spacecop_ml/src/ ./src/
COPY flight/ml/server_main.rs ./src/main.rs
RUN cargo build --release --locked -j2 && \
    strip --strip-debug /ml/target/release/spacecop_ml
RUN strip --strip-unneeded /ml/target/release/spacecop_ml

# Assemble only the server, generated database, and inference-time model files.
FROM debian:trixie-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f AS runtime
ARG APT_SNAPSHOT
LABEL org.opencontainers.image.title="SpaceCOP ML inference runtime with generated parser database" \
      lab.build.apt-snapshot="${APT_SNAPSHOT}" \
      lab.ml.parser-source="supplied COSMOS target definitions" \
      lab.ml.rust-toolchain="1.85.1"
# libgcc-s1 is already part of this digest-pinned base. Its GCC/GDB Python
# pretty-printers are inert here (the image has neither Python nor GDB).
RUN rm -rf /usr/share/gcc/python /usr/share/gdb
COPY --from=compiler /ml/target/release/spacecop_ml /usr/local/bin/spacecop_ml
COPY --from=database /ml/instance/ /opt/spacecop_ml/instance/
COPY --from=database /runtime-models/ /opt/spacecop_ml/scml_models/
WORKDIR /opt/spacecop_ml
USER 1000:1000
ENTRYPOINT ["spacecop_ml"]

