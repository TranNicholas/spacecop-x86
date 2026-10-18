#!/bin/sh
set -eu

# A restart starts a new evidence run instead of replacing earlier logs.
run_directory="/var/log/zeek/runs/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$run_directory"
cd "$run_directory"
exec zeek -C -i eth0 /usr/local/zeek/share/zeek/site/site.zeek
