"""Thread-safe state for the simulated PiSat devices."""

import errno
import threading
from dataclasses import dataclass, field


DEFAULT_REGISTERS = {0: 0x399F, 5: 0}


class DeviceError(OSError):
    """A device failure that should cross the Linux adapter boundary."""


@dataclass
class INA219:
    """INA219 behavior exercised by the upstream EPS driver."""

    volts: float
    milliamps: float
    present: bool = True
    registers: dict = field(default_factory=lambda: dict(DEFAULT_REGISTERS))

    def write(self, register, value):
        if not self.present:
            raise DeviceError(errno.EREMOTEIO, "I2C transaction NACK")
        if register == 0 and value & 0x8000:
            self.registers = dict(DEFAULT_REGISTERS)
        else:
            self.registers[register] = value

    def read(self, register):
        if not self.present:
            raise DeviceError(errno.EREMOTEIO, "I2C transaction NACK")
        if register == 1:  # Shunt voltage, 10 uV per bit.
            return round(self.milliamps * 10) & 0xFFFF
        if register == 2:  # Bus voltage, 4 mV per bit at bits 3..15.
            return (round(self.volts / 0.004) << 3) | 2
        if register == 4:  # Current is zero until the driver calibrates the chip.
            raw = round(self.milliamps / 0.1 * self.registers.get(5, 0) / 4096)
            return raw & 0xFFFF
        return self.registers.get(register, 0)


class Devices:
    """Runtime state for the simulated devices."""

    def __init__(self, settings):
        self.lock = threading.RLock()
        self.sensors = {
            (item["bus"], item["address"]): INA219(
                item["volts"], item["milliamps"], item["present"])
            for item in settings["eps"]
        }
        self.payload = dict(settings["payload"]["values"])
        self.thermal_millidegrees = settings["thermal_millidegrees"]

    def serial_record(self):
        """Encode the exact token format parsed by the upstream payload app."""
        p = self.payload
        return (
            f"_START_FLAG_OK BME280 {p['temperature']:.2f} {p['pressure']:.2f} "
            f"{p['altitude']:.2f} {p['humidity']:.2f} MPU6050 {p['gx']:.2f} "
            f"{p['gy']:.2f} {p['gz']:.2f} {p['ax']:.2f} {p['ay']:.2f} "
            f"{p['az']:.2f} "
            f"GPS {p['latitude']:.4f} {p['longitude']:.4f} {p['gps_altitude']:.2f} "
            f"TMP {p['temperature']:.2f}_END_FLAG_\r\n"
        ).encode()
