"""Implement the subset of rpicam-still used by the upstream camera app."""

import argparse
import json
import os
from pathlib import Path
import time

from PIL import Image

MAX_DIMENSION = 4096


def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--help", action="help")
    parser.add_argument("--nopreview", action="store_true")
    parser.add_argument("--timeout", "-t", type=int, default=1000)
    parser.add_argument("--width", "-w", type=int, default=640)
    parser.add_argument("--height", "-h", type=int, default=480)
    parser.add_argument("-o", required=True, dest="output")
    return parser.parse_args()


def main():
    args = parse_args()
    profile = json.loads(Path(os.environ["SIL_RUNTIME_PROFILE"]).read_text())
    camera = profile["devices"]["camera"]
    valid_size = (
        1 <= args.width <= MAX_DIMENSION and 1 <= args.height <= MAX_DIMENSION
    )
    if camera["fail"] or not valid_size:
        return 1

    time.sleep(camera["latency_seconds"])
    image = Image.new("RGB", (args.width, args.height), tuple(camera["color"]))
    image.save(args.output, format="JPEG", quality=90)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
