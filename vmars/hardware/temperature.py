"""SHT31-D ambient temperature reading over the Orange Pi I2C bus."""

from __future__ import annotations

import logging
import threading
import time

from vmars import config
from vmars.hardware.i2c import open_bus
from vmars.hardware.protocol import sht31_raw_to_celsius

log = logging.getLogger(__name__)

_CMD_SOFT_RESET = (0x30, 0xA2)
_CMD_SINGLE_SHOT_HIGH_REPEATABILITY = (0x24, 0x00)
_CONVERSION_TIME_S = 0.02


class Sht31TemperatureSensor:
    """Polls the SHT31-D twice per second in a background thread."""

    def __init__(self, bus_num: int = config.I2C_BUS, address: int = config.SHT31_ADDRESS):
        self.bus_num = bus_num
        self.address = address
        self._bus = None
        self._ok = False
        self._temperature = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.stop()
        self._stop.clear()
        try:
            self._bus = open_bus(self.bus_num)
            self._bus.write_byte_data(self.address, *_CMD_SOFT_RESET)
            time.sleep(0.05)
            self._ok = True
            log.info("Temperature sensor OK (SHT31-D on I2C bus %s)", self.bus_num)
        except Exception as exc:  # noqa: BLE001
            self._ok = False
            log.error("Temperature sensor error on I2C bus %s: %s", self.bus_num, exc)

        self._thread = threading.Thread(target=self._run, name="sht31", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._bus:
            try:
                self._bus.close()
            except Exception:  # noqa: BLE001
                pass
            self._bus = None

    def get_temperature(self) -> float:
        with self._lock:
            return self._temperature

    def _run(self) -> None:
        while not self._stop.is_set():
            if self._ok:
                try:
                    self._bus.write_byte_data(self.address, *_CMD_SINGLE_SHOT_HIGH_REPEATABILITY)
                    time.sleep(_CONVERSION_TIME_S)
                    data = self._bus.read_i2c_block_data(self.address, 0x00, 6)
                    celsius = sht31_raw_to_celsius((data[0] << 8) | data[1])
                    with self._lock:
                        self._temperature = celsius
                except Exception:  # noqa: BLE001 - transient I2C noise
                    pass
            self._stop.wait(config.TEMP_POLL_S)
