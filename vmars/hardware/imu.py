"""MPU-6050 pitch reading over the Orange Pi I2C bus."""

from __future__ import annotations

import logging
import math
import threading

from vmars import config
from vmars.hardware.i2c import open_bus
from vmars.hardware.protocol import to_int16, wrap_degrees

log = logging.getLogger(__name__)

_REG_PWR_MGMT_1 = 0x6B
_REG_ACCEL_XOUT_H = 0x3B


class Mpu6050Imu:
    """Polls the accelerometer in a background thread and exposes the pitch.

    Sampling only happens while :attr:`reading_active` is True. The motion
    controllers switch it on near the shape's crucial angles, which keeps the
    I2C bus quiet (and the log readable) while the platform is tumbling.
    """

    def __init__(
        self,
        bus_num: int = config.I2C_BUS,
        address: int = config.MPU6050_ADDRESS,
        pitch_offset_deg: float = config.IMU_PITCH_OFFSET_DEG,
    ):
        self.bus_num = bus_num
        self.address = address
        self.pitch_offset_deg = pitch_offset_deg
        self.reading_active = False

        self._bus = None
        self._ok = False
        self._pitch = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sample_count = 0

    # ── lifecycle ────────────────────────────────────────────────────────────
    def start(self) -> None:
        self.stop()
        self._stop.clear()
        self.reading_active = False
        try:
            self._bus = open_bus(self.bus_num)
            self._bus.write_byte_data(self.address, _REG_PWR_MGMT_1, 0)  # wake up
            self._ok = True
            log.info("IMU OK (I2C bus %s)", self.bus_num)
        except Exception as exc:  # noqa: BLE001
            self._ok = False
            log.error("IMU error on I2C bus %s: %s", self.bus_num, exc)

        if config.IMU_AUTO_ZERO_ON_START:
            self.set_zero_here()

        self._thread = threading.Thread(target=self._run, name="imu", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.reading_active = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.5)
            self._thread = None
        if self._bus:
            try:
                self._bus.close()
            except Exception:  # noqa: BLE001
                pass
            self._bus = None

    # ── public API ───────────────────────────────────────────────────────────
    @property
    def is_ok(self) -> bool:
        return self._ok

    def get_pitch(self) -> float:
        """Latest pitch in degrees, wrapped to [-180, 180)."""
        with self._lock:
            return wrap_degrees(self._pitch)

    def set_zero_here(self) -> None:
        """Use the current orientation as 0°."""
        if not self._ok:
            return
        try:
            raw = self._read_raw_angle()
        except Exception:  # noqa: BLE001
            return
        with self._lock:
            self.pitch_offset_deg = raw

    # ── internals ────────────────────────────────────────────────────────────
    def _read_raw_angle(self) -> float:
        data = self._bus.read_i2c_block_data(self.address, _REG_ACCEL_XOUT_H, 6)
        ax = to_int16(data[0], data[1])
        az = to_int16(data[4], data[5])
        return math.degrees(math.atan2(ax, az))

    def _run(self) -> None:
        while not self._stop.is_set():
            if self._ok and self.reading_active:
                try:
                    angle = (self._read_raw_angle() - self.pitch_offset_deg) % 360.0
                    with self._lock:
                        self._pitch = angle
                    self._sample_count += 1
                    if self._sample_count % config.IMU_LOG_EVERY_N == 0:
                        log.info("IMU pitch: %.1f°", angle)
                except Exception:  # noqa: BLE001 - transient I2C noise
                    pass
            self._stop.wait(config.IMU_POLL_S)
