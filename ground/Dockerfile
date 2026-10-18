# Build the supplied PiSat plugin without retaining its source tree in the
# one-shot installer image.
FROM openc3inc/openc3-cosmos-cmd-tlm-api:7.2.1@sha256:8611c1e3b2db2dc07182f78ee849271b36a84714463a59d05a1062aff08c514a AS build
USER root
COPY upstream/spacecop-demo/gsw/openc3-cosmos-cfs/ /opt/spacecop-plugin/
COPY ground/openc3-cosmos-cfs.gemspec /opt/spacecop-plugin/openc3-cosmos-cfs.gemspec
COPY ground/procedures/arm.py /opt/spacecop-plugin/targets/TO_LAB/procedures/arm.py
WORKDIR /opt/spacecop-plugin
RUN test ! -e pyproject.toml && \
    test -f requirements.txt && \
    test "$(grep -Ev '^[[:space:]]*(#|$)' requirements.txt | wc -l)" -eq 0 && \
    rm -f requirements.txt && \
    procedure_count="$(find targets -type f -path '*/procedures/procedure.py' | wc -l)" && \
    test "$procedure_count" -eq 19 && \
    find targets -type f -path '*/procedures/procedure.py' -exec rm -f {} \; && \
    empty_utility_count=0 && \
    for file in targets/*/lib/*.py; do \
      if grep -q '^    def utility(self):$' "$file" && grep -q '^        pass$' "$file"; then \
        rm -f "$file"; \
        empty_utility_count=$((empty_utility_count + 1)); \
      fi; \
    done && \
    test "$empty_utility_count" -eq 19 && \
    rm -rf microservices/TEST microservices/TEST2 && \
    find . -type d -name __pycache__ -prune -exec rm -rf {} \; && \
    test -f targets/CAMERA/procedures/day_in_the_life.py && \
    test -f targets/EPS/lib/battery_soc_conversion.py && \
    test -f targets/EPS/lib/solar_panel_power_conversion.py && \
    test -f targets/EPS/lib/total_solar_power_conversion.py && \
    test -f targets/SC/lib/bit_field_conversion.py && \
    test -f microservices/CFDP/cfdp.py && \
    VERSION="0.1.$(( 0x$(find . -type f | sort | xargs sha256sum | sha256sum | cut -c1-7) ))" && \
    VERSION="$VERSION" gem build openc3-cosmos-cfs.gemspec && \
    printf '{"target_ip":"flight"}\n' > variables.json

# Runtime holds only the packaged artifact and its install variables.
FROM openc3inc/openc3-cosmos-cmd-tlm-api:7.2.1@sha256:8611c1e3b2db2dc07182f78ee849271b36a84714463a59d05a1062aff08c514a AS runtime
LABEL org.opencontainers.image.title="COSMOS 7.2.1 supplied PiSat plugin installer" \
      lab.ground.plugin-identity="content-derived gem version"
USER root
COPY --from=build /opt/spacecop-plugin/*.gem /opt/spacecop-plugin/
COPY --from=build /opt/spacecop-plugin/variables.json /opt/spacecop-plugin/variables.json
WORKDIR /opt/spacecop-plugin
USER 1001:1001

# This runs after stock COSMOS initialization. It is necessarily a runtime
# one-shot because password setup and plugin loading require the live API.
ENTRYPOINT ["sh", "-ec", "set -- /opt/spacecop-plugin/*.gem; if [ \"$#\" -ne 1 ] || [ ! -f \"$1\" ]; then echo 'Expected exactly one packaged plugin' >&2; exit 1; fi; password_output=\"$(openc3cli setpassword 2>&1)\" || case \"$password_output\" in *'Password has already been set'*) ;; *) printf 'Password initialization failed: %s\\n' \"$password_output\" >&2; exit 1 ;; esac; openc3cli list DEFAULT >/dev/null; openc3cli load \"$1\" DEFAULT --variables /opt/spacecop-plugin/variables.json; installed=\"$(openc3cli list DEFAULT)\"; gem_name=\"$(basename \"$1\" .gem)\"; case \"$installed\" in *\"$gem_name\"*) ;; *) printf 'Plugin %s was loaded but is not installed:\\n%s\\n' \"$gem_name\" \"$installed\" >&2; exit 1 ;; esac; digest=\"$(sha256sum \"$1\" | cut -d ' ' -f 1)\"; printf 'installed plugin %s sha256 %s\\n' \"$gem_name\" \"$digest\""]
