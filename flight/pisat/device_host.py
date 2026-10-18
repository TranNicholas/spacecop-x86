"""Present the configured device models through Linux-compatible interfaces."""

import os
import pty
import time
from pathlib import Path

import gi

gi.require_version("UMockdev", "1.0")
from gi.repository import UMockdev

from .i2c import I2C
from .models import Devices


class DeviceHost:
    """Adapt device models to Linux without knowing flight process lifecycle."""

    def __init__(self, settings):
        self.settings = settings
        self.devices = Devices(settings["devices"])

        self.testbed = UMockdev.Testbed.new()
        self.i2c = I2C(self.testbed, self.devices)  # Retains the GI handlers.
        thermal = Path(self.testbed.get_root_dir()) / "sys/class/thermal/thermal_zone0/temp"
        thermal.parent.mkdir(parents=True, exist_ok=True)
        thermal.write_text(f"{self.devices.thermal_millidegrees}\n")

        self.serial_master, self.serial_slave = pty.openpty()
        serial_path = Path(settings["serial_path"])
        if serial_path.is_symlink():
            serial_path.unlink()
        serial_path.symlink_to(os.ttyname(self.serial_slave))
        os.set_blocking(self.serial_master, False)
        self.next_serial = time.monotonic()

    def child_environment(self):
        return {"UMOCKDEV_DIR": self.testbed.get_root_dir(),
                "LD_PRELOAD": self.settings["preload"]}

    def feed_payload(self):
        """Write one payload record when its configured period has elapsed."""
        now = time.monotonic()
        if now < self.next_serial:
            return
        record = self.devices.serial_record()
        try:
            os.write(self.serial_master, record)
        except BlockingIOError:
            pass
        self.next_serial = now + self.settings["devices"]["payload"]["period_seconds"]

    def shutdown(self):
        os.close(self.serial_master)
        os.close(self.serial_slave)
