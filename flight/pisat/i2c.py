"""Expose the INA219 models through umockdev's Linux I2C ABI."""

import errno
import struct

import gi

gi.require_version("UMockdev", "1.0")
from gi.repository import UMockdev


I2C_SLAVE = 0x0703


class I2C:
    """Attach one umockdev handler per configured I2C bus."""

    def __init__(self, testbed, devices):
        self.devices = devices
        self._handlers = []  # GI handlers must live as long as the adapter.
        self._descriptors = {}

        for bus in sorted({bus for bus, _address in devices.sensors}):
            self._attach_bus(testbed, bus)

    def _attach_bus(self, testbed, bus):
        name = bus.rsplit("/", 1)[1]
        testbed.add_from_string(f"P: /devices/{name}\nN: {name}\nE: SUBSYSTEM=i2c-dev\n")
        handler = UMockdev.IoctlBase()
        handler.connect("handle-ioctl", self.ioctl, bus)
        handler.connect("handle-read", self.read, bus)
        handler.connect("handle-write", self.write, bus)
        handler.connect("client-vanished", self._client_vanished)
        testbed.attach_ioctl(bus, handler)
        self._handlers.append(handler)

    def _client_vanished(self, _handler, client):
        self._descriptors.pop(client, None)

    def _descriptor(self, client):
        return self._descriptors.setdefault(client, {"address": None, "pointer": 0})

    def ioctl(self, _handler, client, _bus):
        if client.get_request() != I2C_SLAVE:
            client.complete(-1, errno.ENOTTY)
            return True

        address = int.from_bytes(bytes(client.get_arg().retrieve()), "little")
        if not 0 <= address <= 0x7F:
            client.complete(-1, errno.EINVAL)
        else:
            self._descriptor(client)["address"] = address
            client.complete(0, 0)
        return True

    def _sensor(self, client, bus):
        descriptor = self._descriptor(client)
        sensor = self.devices.sensors.get((bus, descriptor["address"]))
        if sensor is None or not sensor.present:
            raise OSError(errno.EREMOTEIO, "I2C transaction NACK")
        return descriptor, sensor

    def read(self, _handler, client, bus):
        try:
            with self.devices.lock:
                descriptor, sensor = self._sensor(client, bus)
                requested = len(client.get_arg().retrieve())
                data = struct.pack(">H", sensor.read(descriptor["pointer"]))[:requested]
                client.get_arg().update(0, data)
                client.complete(len(data), 0)
        except OSError as exc:
            client.complete(-1, exc.errno)
        return True

    def write(self, _handler, client, bus):
        try:
            with self.devices.lock:
                descriptor, sensor = self._sensor(client, bus)
                data = bytes(client.get_arg().retrieve())
                if len(data) not in (1, 3):
                    raise OSError(errno.EINVAL, "Unsupported INA219 transaction size")

                descriptor["pointer"] = data[0]
                if len(data) == 3:
                    sensor.write(data[0], int.from_bytes(data[1:], "big"))
                client.complete(len(data), 0)
        except OSError as exc:
            client.complete(-1, exc.errno)
        return True
