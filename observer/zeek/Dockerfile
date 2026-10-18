# Generate the analyzer without retaining its Python generator or source
# definitions in the witness image.
FROM zeek/zeek:8.0.10@sha256:73e80e9cd23ff71fd28d158e9a9af5c7b2b0ef5d4036af61521827531347c0e3 AS build
USER root
COPY upstream/spacecop-demo/gsw/cosmos_to_zeek.py /generator/cosmos_to_zeek.py
COPY upstream/spacecop-demo/gsw/openc3-cosmos-cfs/targets/ /generator/targets/
RUN mkdir /generated && \
    python3 -I /generator/cosmos_to_zeek.py /generator/targets \
        --output /generated/ccsds_analyzer.zeek \
        --json /generated/ccsds_definitions.json \
        --summary /generated/ccsds_summary.txt

# Image: independent Zeek witness with the generated CCSDS analyzer.
FROM zeek/zeek:8.0.10@sha256:73e80e9cd23ff71fd28d158e9a9af5c7b2b0ef5d4036af61521827531347c0e3 AS runtime
LABEL org.opencontainers.image.title="SpaceCOP independent Zeek witness" \
      lab.zeek.analyzer-source="supplied generator and COSMOS target definitions"
USER root
COPY --from=build /generated/ /usr/local/zeek/share/zeek/site/
COPY observer/zeek/site.zeek /usr/local/zeek/share/zeek/site/site.zeek
COPY --chmod=755 observer/zeek/entrypoint.sh /usr/local/bin/run-zeek
RUN set -eu; \
    site=/usr/local/zeek/share/zeek/site; \
    cd /tmp; zeek -C -b "$site/site.zeek"
ENTRYPOINT ["run-zeek"]
