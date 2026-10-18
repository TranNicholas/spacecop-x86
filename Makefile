# Thin analyst commands. Component topology lives in the Compose files.
COMPOSE := docker compose
# The same Compose graph builds both flight ABIs; only architecture and lab identity vary.
QEMU_ENV := COMPOSE_PROJECT_NAME=spacecop-armhf FLIGHT_PLATFORM=linux/arm/v7 FLIGHT_SIMULATION=arm-linux-gnueabihf FLIGHT_IMAGE=spacecop-lab/flight-armhf:local ML_IMAGE=spacecop-lab/ml-armhf:local LAB_UI_PORT=2911 LAB_ELASTIC_PORT=19911 LAB_KIBANA_PORT=15911 LAB_INSTANCE=armhf
BROWSER_HEALTH := $(COMPOSE) --profile health run --rm --no-deps browser-health
PYTHON := PYTHONDONTWRITEBYTECODE=1 python3

.DEFAULT_GOAL := help
.PHONY: help prepare up arm health compare evidence recreate-sidecars down clean qemu-up qemu-arm qemu-health qemu-compare qemu-evidence qemu-recreate-sidecars qemu-down qemu-clean

help: ## Show tasks. [state] changes the lab; [DESTRUCTIVE] deletes data.
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) \
		| sed -E 's/^([a-z-]+):.*## /\1\t/' \
		| column -t -s "$$(printf '\t')"

prepare: ## Initialize the pinned SpaceCOP fork and its nested submodules.
	git submodule update --init --recursive --jobs 4
	@test -z "$$(git -C upstream/spacecop-demo status --porcelain)" || { \
		echo 'SpaceCOP fork has local changes' >&2; exit 1; \
	}

up: prepare ## [state] Build and start the lab. TO_LAB stays disarmed, as supplied.
	$(COMPOSE) up -d --build

# Compose cannot wait on a one-shot that has already exited, so poll its state.
arm: ## [state] Enable the TO_LAB downlink to COSMOS (stock command; enters every capture).
	@until test -n "$$($(COMPOSE) ps -a -q --status exited ground-bootstrap)"; do \
		sleep 2; \
	done
	@$(PYTHON) -c 'from evaluation.cosmos_api import CosmosApi; from evaluation.health_check import interface_ready; print(interface_ready(CosmosApi.from_environment()))'
	$(COMPOSE) run --rm --no-deps --entrypoint openc3cli ground-bootstrap \
		script run TO_LAB/procedures/arm.py

health: ## [state] Diagnose services, web endpoints, login, telemetry, and observer flow.
	@status=0; \
	$(PYTHON) -m evaluation.health_check || status=1; \
	if test -n "$$($(COMPOSE) ps -q --status running openc3-traefik)"; then \
		mkdir -p evaluation/output/$${LAB_INSTANCE:-sitl}/browser; \
		$(BROWSER_HEALTH) || status=1; \
	else \
		echo 'SKIP  COSMOS browser           openc3-traefik is not running'; \
	fi; \
	exit $$status

compare: ## [state] Probe CAMERA/CI_LAB bytes, effects, and replay in this lane.
	@$(PYTHON) -m evaluation.arch_compare

evidence: ## Collect one receipt under evaluation/output/ (does not start or repair anything).
	$(PYTHON) -m evaluation.receipt

recreate-sidecars: ## [state] Recreate ml, capture and witness-zeek in flight's current namespaces.
	$(COMPOSE) up -d --force-recreate --no-deps ml capture witness-zeek

down: ## [state] Stop; named volumes (COSMOS, mission data, evidence) are retained.
	$(COMPOSE) down

clean: ## [DESTRUCTIVE] Delete this lab's containers and named volumes.
	$(COMPOSE) down -v

qemu-up: ## [state] Build and start the isolated 32-bit Arm QEMU comparison lab.
	$(QEMU_ENV) $(MAKE) up

qemu-arm: ## [state] Arm telemetry in the Arm comparison lab.
	$(QEMU_ENV) $(MAKE) arm

qemu-health: ## [state] Check the Arm lab; arms telemetry and sends EPS NOOP.
	$(QEMU_ENV) $(MAKE) health

qemu-compare: ## [state] Run the same command/effect probe in the Arm lab.
	@$(QEMU_ENV) $(MAKE) --no-print-directory compare

qemu-evidence: ## Collect a receipt and captures from the Arm lab.
	$(QEMU_ENV) $(MAKE) evidence

qemu-recreate-sidecars: ## [state] Reattach Arm ML, capture, and Zeek to flight.
	$(QEMU_ENV) $(MAKE) recreate-sidecars

qemu-down: ## [state] Stop the Arm lab; keep its volumes.
	$(QEMU_ENV) $(MAKE) down

qemu-clean: ## [DESTRUCTIVE] Delete the Arm lab's containers and named volumes.
	$(QEMU_ENV) $(MAKE) clean
