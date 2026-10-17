"""JRT laser distance sensors (single-shot mode).

Two physical sensors are used:

* **S1** on ``/dev/ttyUSB0`` — one reading per measurement window.
* **S2** on ``/dev/ttyUSB1`` — *dual mode*: its first valid reading is reported
  as S2 and its second valid reading as S3. This is how three thickness points
  are obtained from two sensors.
"""

from __future__ import annotations

import logging
import threading
import time

import serial

from vmars import config
from vmars.hardware import protocol as jrt

log = logging.getLogger(__name__)


class LaserSensorWorker(threading.Thread):
    """Owns one JRT sensor: initialises it, fires single shots and keeps the
    best reading seen since the last :meth:`reset_best`."""

    def __init__(
        self,
        port: str,
        label: str,
        start_delay_s: float = 0.0,
        dual_mode: bool = False,
        baudrate: int = config.JRT_BAUDRATE,
    ):
        super().__init__(name=f"jrt-{label}", daemon=True)
        self.port = port
        self.label = label
        self.start_delay_s = start_delay_s
        self.dual_mode = dual_mode
        self.baudrate = baudrate

        self.is_connected = False
        self._serial: serial.Serial | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._logging_enabled = threading.Event()  # set = inside measurement window

        self._reset_best_locked()

    # ── measurement bookkeeping ──────────────────────────────────────────────
    def _reset_best_locked(self) -> None:
        self.best_distance_mm = 0.0
        self.best_quality = -1
        self.best_latency_ms = 0.0
        self.second_distance_mm = 0.0  # dual mode → S3
        self.second_quality = -1
        self.valid_count = 0
        self.valid_finish_time = 0.0   # perf_counter() of the reading that completed the set

    def reset_best(self) -> None:
        with self._lock:
            self._reset_best_locked()

    def set_logging(self, enabled: bool) -> None:
        """Only print readings to the log during the official measurement window."""
        if enabled:
            self._logging_enabled.set()
        else:
            self._logging_enabled.clear()

    def best_distance(self) -> float:
        with self._lock:
            return self.best_distance_mm

    def second_distance(self) -> float:
        with self._lock:
            return self.second_distance_mm

    def has_valid_reading(self) -> bool:
        """True once a usable reading exists. A disconnected sensor never
        blocks the process, so it always counts as valid."""
        if not self.is_connected:
            return True
        with self._lock:
            first_ok = 0 < self.best_distance_mm < config.JRT_VALID_MAX_MM
            if self.dual_mode:
                return first_ok and 0 < self.second_distance_mm < config.JRT_VALID_MAX_MM
            return first_ok

    def _record(self, distance_mm: int, quality: int, latency_ms: float) -> None:
        """Keep the reading if it improves the current set (caller holds lock)."""
        if not 0 < distance_mm < config.JRT_VALID_MAX_MM:
            return
        if self.dual_mode:
            if self.valid_count == 0:
                self.best_distance_mm, self.best_quality = distance_mm, quality
                self.best_latency_ms = latency_ms
                self.valid_count = 1
            elif self.valid_count == 1:
                self.second_distance_mm, self.second_quality = distance_mm, quality
                self.valid_count = 2
                self.valid_finish_time = time.perf_counter()
        elif quality > self.best_quality or self.best_quality == -1:
            self.best_distance_mm, self.best_quality = distance_mm, quality
            self.best_latency_ms = latency_ms
            self.valid_finish_time = time.perf_counter()

    # ── thread body ──────────────────────────────────────────────────────────
    def run(self) -> None:
        try:
            self._serial = serial.Serial(self.port, self.baudrate, timeout=1)
            self.is_connected = True
            log.info("Initialising JRT sensor %s on %s", self.label, self.port)
            self._initialise_sensor()

            if self.start_delay_s > 0:
                self._stop_event.wait(self.start_delay_s)

            while not self._stop_event.is_set():
                cycle_start = time.time()
                self._fire_single_shot()
                elapsed = time.time() - cycle_start
                self._stop_event.wait(max(0.1, config.JRT_SHOT_INTERVAL_S - elapsed))
        except Exception as exc:  # noqa: BLE001
            self.is_connected = False
            log.error("JRT sensor %s (%s) failed: %s", self.label, self.port, exc)

    def _initialise_sensor(self) -> None:
        ser = self._serial
        # Clean up after a previous session that may have left the laser on.
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.write(jrt.CMD_LASER_OFF)
        time.sleep(0.1)
        ser.read(ser.in_waiting)

        # Hardware reset through DTR/RTS.
        ser.dtr = ser.rts = True
        time.sleep(0.1)
        ser.dtr = ser.rts = False
        time.sleep(0.15)

        for command in (jrt.CMD_AUTO_BAUD, jrt.CMD_READ_VOLTAGE):
            ser.write(command)
            time.sleep(0.5)
            ser.read(ser.in_waiting)

        # Stagger laser turn-on per sensor to limit the inrush current.
        sensor_index = int(self.label.lstrip("S") or 1)
        time.sleep(0.5 * sensor_index)
        ser.write(jrt.CMD_LASER_ON)
        time.sleep(0.8)
        ser.read(ser.in_waiting)

    def _fire_single_shot(self) -> None:
        ser = self._serial
        ser.write(jrt.CMD_SINGLE_SHOT_AUTO)
        shot_time = time.perf_counter()

        while time.perf_counter() - shot_time < config.JRT_REPLY_TIMEOUT_S and not self._stop_event.is_set():
            if ser.in_waiting > 0 and ser.read(1) == bytes([jrt.JRT_FRAME_HEADER]):
                body = ser.read(jrt.JRT_FRAME_BODY_LEN)
                if len(body) == jrt.JRT_FRAME_BODY_LEN:
                    latency_ms = (time.perf_counter() - shot_time) * 1000.0
                    reading = jrt.parse_jrt_frame(body)
                    if reading.distance_mm <= config.JRT_PLAUSIBLE_MAX_MM:
                        with self._lock:
                            self._record(reading.distance_mm, reading.quality, latency_ms)
                            shown_label = (
                                f"{self.label} (S3)" if self.dual_mode and self.valid_count >= 2 else self.label
                            )
                        if self._logging_enabled.is_set():
                            log.info(
                                "[%s] distance: %s mm | quality: %s",
                                shown_label, reading.distance_mm, reading.quality,
                            )
                    return
            time.sleep(0.01)

    def stop(self) -> None:
        self._stop_event.set()
        if self._serial and self._serial.is_open:
            try:
                self._serial.write(jrt.CMD_LASER_OFF)
                time.sleep(0.1)  # let the command leave before closing the port
                self._serial.close()
            except Exception:  # noqa: BLE001
                pass


class LaserSensorArray:
    """Facade over S1 and the dual-mode S2 (which also provides S3)."""

    def __init__(self) -> None:
        self.s1: LaserSensorWorker | None = None
        self.s2: LaserSensorWorker | None = None
        self._logging = False

    def start(self) -> None:
        self.stop()
        self.s1 = LaserSensorWorker(config.JRT_S1_PORT, "S1", config.JRT_S1_START_DELAY_S)
        self.s2 = LaserSensorWorker(config.JRT_S2_PORT, "S2", config.JRT_S2_START_DELAY_S, dual_mode=True)
        for sensor in self._sensors():
            sensor.set_logging(self._logging)
            sensor.start()

    def stop(self) -> None:
        for sensor in self._sensors():
            sensor.stop()
            sensor.join(timeout=1.0)

    def _sensors(self) -> list[LaserSensorWorker]:
        return [s for s in (self.s1, self.s2) if s is not None]

    # ── used by the controllers ──────────────────────────────────────────────
    def set_measurement_window(self, active: bool) -> None:
        self._logging = active
        for sensor in self._sensors():
            sensor.set_logging(active)

    def reset(self) -> None:
        for sensor in self._sensors():
            sensor.reset_best()

    def all_valid(self) -> bool:
        if self.s1 is None:
            return False
        return all(sensor.has_valid_reading() for sensor in self._sensors())

    def best_distances(self) -> tuple[float, float, float]:
        """(S1, S2, S3) in millimetres."""
        if self.s1 is None or self.s2 is None:
            return 0.0, 0.0, 0.0
        return self.s1.best_distance(), self.s2.best_distance(), self.s2.second_distance()

    def connected(self) -> tuple[bool, bool, bool]:
        """Connection state for (S1, S2, S3). S3 shares S2's port."""
        s1 = bool(self.s1 and self.s1.is_connected)
        s2 = bool(self.s2 and self.s2.is_connected)
        return s1, s2, s2

    def last_valid_finish_time(self) -> float:
        """perf_counter() of the latest reading that completed a valid set."""
        times = [s.valid_finish_time for s in self._sensors() if s.is_connected]
        return max(times) if times else time.perf_counter()
