# Image: witness-owned packet capture in flight's network namespace.
# Build inputs: pinned Debian image and the shared snapshot date from Compose.
ARG APT_SNAPSHOT=20261005T000000Z
FROM debian:trixie-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f AS runtime
ARG APT_SNAPSHOT
LABEL org.opencontainers.image.title="Independent raw capture for the satellite namespace" \
      lab.build.apt-snapshot="${APT_SNAPSHOT}"
RUN rm /etc/apt/sources.list.d/debian.sources && \
    printf 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/%s/ trixie main\ndeb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/%s/ trixie-security main\n' "$APT_SNAPSHOT" "$APT_SNAPSHOT" > /etc/apt/sources.list && \
    apt-get update && \
    apt-get install --no-install-recommends -y tcpdump && \
    rm -rf /var/lib/apt/lists/*

# Timestamped output: a capture restart starts a new file instead of truncating one.
ENTRYPOINT ["tcpdump"]
CMD ["-i", "any", "-p", "-U", "-Z", "root", "-G", "86400", "-w", "/evidence/traffic-%Y%m%dT%H%M%SZ.pcap", "udp port 5012 or udp port 5013 or tcp port 9111 or tcp port 9112"]
