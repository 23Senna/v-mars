"""Non-blocking link to the ESP32 stepper controller."""

from __future__ import annotations

import logging
import queue
import threading
import time

import serial

from vmars import config
from vmars.hardware.protocol import format_motor_command

log = logging.getLogger(__name__)


class Esp32MotorLink:
    """Sends motion commands from a background thread so the GUI never blocks.

    Identical consecutive commands are dropped: re-sending the same target makes
    AccelStepper re-plan its ramp, which shows up as drift / stutter.
    """

    _QUEUE_SIZE = 10

    def __init__(self, port: str = config.ESP32_PORT, baudrate: int = config.ESP32_BAUDRATE):
        self.port = port
        self.baudrate = baudrate
        self._serial: serial.Serial | None = None
        self._stop = threading.Event()
        self._tx_queue: queue.Queue[str] = queue.Queue(maxsize=self._QUEUE_SIZE)
        self._threads: list[threading.Thread] = []
        self._last_command = ""

    # ── lifecycle ────────────────────────────────────────────────────────────
    def start(self) -> None:
        self.stop()  # never run two TX threads on the same port
        self._stop.clear()
        self._last_command = ""
        try:
            # write_timeout keeps a stuck UART from freezing the TX thread.
            self._serial = serial.Serial(self.port, self.baudrate, timeout=0.1, write_timeout=0.1)
        except Exception as exc:  # noqa: BLE001 - keep running without hardware
            log.error("ESP32 serial error on %s: %s", self.port, exc)
            self._serial = None

        self._threads = [
            threading.Thread(target=self._drain_rx, name="esp32-rx", daemon=True),
            threading.Thread(target=self._transmit, name="esp32-tx", daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=0.5)
        self._threads = []
        self._flush_pending()  # e.g. the final "roll speed 0" command
        if self._serial:
            try:
                self._serial.close()
            except Exception:  # noqa: BLE001
                pass
            self._serial = None

    # ── public API ───────────────────────────────────────────────────────────
    def send(self, pitch_steps: float, roll_speed: float, yaw_steps: float) -> None:
        command = format_motor_command(pitch_steps, roll_speed, yaw_steps)
        if command == self._last_command:
            return
        self._last_command = command

        if self._tx_queue.full():  # keep the newest command, drop the oldest
            try:
                self._tx_queue.get_nowait()
            except queue.Empty:
                pass
        self._tx_queue.put(command)

    def _flush_pending(self) -> None:
        while True:
            try:
                command = self._tx_queue.get_nowait()
            except queue.Empty:
                return
            try:
                if self._serial:
                    self._serial.write(command.encode("utf-8"))
                    self._serial.flush()
            except Exception:  # noqa: BLE001
                pass

    # ── worker threads ───────────────────────────────────────────────────────
    def _drain_rx(self) -> None:
        """Discard ESP32 debug output so the OS buffer never fills up."""
        while not self._stop.is_set():
            try:
                if self._serial and self._serial.in_waiting:
                    self._serial.read(self._serial.in_waiting)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.05)

    def _transmit(self) -> None:
        while not self._stop.is_set():
            try:
                command = self._tx_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                if self._serial:
                    self._serial.write(command.encode("utf-8"))
                    self._serial.flush()
            except Exception as exc:  # noqa: BLE001
                log.debug("ESP32 write failed: %s", exc)
