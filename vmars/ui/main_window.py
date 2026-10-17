"""Main window: wires the screens, the hardware drivers and the controllers.

Responsibilities are split as follows:

* ``vmars.control``  decides *what* the motors do (pure logic, unit-tested)
* ``vmars.hardware`` talks to the devices (serial / I2C, background threads)
* ``vmars.storage``  logs every run to PostgreSQL (background thread)
* this module        moves data between them on two Qt timers:
    - control tick (100 ms): motion state machine → ESP32
    - UI tick (1 s):        countdown, plots, drying supervision
"""

from __future__ import annotations

import logging
import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QDialog, QMainWindow, QMessageBox, QStackedWidget

from vmars import config
from vmars.control import (
    AutoController,
    DryingAction,
    DryingMonitor,
    ManualController,
    MotionOffsets,
    TickResult,
)
from vmars.control.sequences import ManualPreset
from vmars.hardware.esp32 import Esp32MotorLink
from vmars.hardware.imu import Mpu6050Imu
from vmars.hardware.laser import LaserSensorArray
from vmars.hardware.temperature import Sht31TemperatureSensor
from vmars.storage.database import HistoryRepository, ProcessRecord
from vmars.ui import style
from vmars.ui.dialogs import CalibrationDialog, CorrectionDialog
from vmars.ui.screens import DatabaseScreen, InputScreen, MainMenuScreen, MonitorScreen
from vmars.ui.widgets import MotionNudger

log = logging.getLogger(__name__)

PAGE_MENU, PAGE_INPUT, PAGE_MONITOR, PAGE_DATABASE = range(4)


def now_ms() -> float:
    return time.time() * 1000.0


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("V-MARS")
        self.setStyleSheet(style.APP_STYLE)

        # Hardware
        self.motors = Esp32MotorLink()
        self.imu = Mpu6050Imu()
        self.thermometer = Sht31TemperatureSensor()
        self.lasers = LaserSensorArray()

        # Process state
        self.offsets = MotionOffsets()
        self.nudger = MotionNudger(self.offsets, self)
        self.drying = DryingMonitor()
        self.controller: AutoController | ManualController | None = None
        self.running = False
        self.paused = False
        self.time_remaining_s = 0.0
        self.thickness = (0.0, 0.0, 0.0)
        self.response_time_ms = 0.0
        self._warning_box: QMessageBox | None = None
        self._correction_dialog: CorrectionDialog | None = None

        # Database
        self.history = HistoryRepository(parent=self)
        self.history_limit = config.DB_HISTORY_PAGE_SIZE
        db_ok = self.history.initialise()
        self.history.start()

        # Screens
        self.menu_screen = MainMenuScreen()
        self.input_screen = InputScreen()
        self.monitor_screen = MonitorScreen()
        self.database_screen = DatabaseScreen()
        self.stack = QStackedWidget()
        for screen in (self.menu_screen, self.input_screen, self.monitor_screen, self.database_screen):
            self.stack.addWidget(screen)
        self.setCentralWidget(self.stack)
        self.menu_screen.set_database_status(db_ok)

        self._connect_signals()
        self.monitor_screen.set_mode(self.input_screen.mode)
        self._load_history()

        # Timers
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._on_ui_tick)
        self.ui_timer.start(config.UI_PERIOD_MS)

        self.control_timer = QTimer(self)
        self.control_timer.timeout.connect(self._on_control_tick)

    def _connect_signals(self) -> None:
        go = self.stack.setCurrentIndex
        self.menu_screen.open_input.connect(lambda: go(PAGE_INPUT))
        self.menu_screen.open_monitoring.connect(lambda: go(PAGE_MONITOR))
        self.menu_screen.open_database.connect(self._open_database)

        self.input_screen.mode_changed.connect(self.monitor_screen.set_mode)
        self.input_screen.start_requested.connect(self.start_process)
        self.input_screen.back_requested.connect(lambda: go(PAGE_MENU))

        self.monitor_screen.stop_requested.connect(self.stop_process)
        self.monitor_screen.pause_requested.connect(self.toggle_pause)
        self.monitor_screen.back_requested.connect(lambda: go(PAGE_MENU))
        self.monitor_screen.preset_selected.connect(self._on_preset_selected)
        self.monitor_screen.normal_requested.connect(self._on_normal_requested)

        self.database_screen.load_more_requested.connect(self._load_more_history)
        self.database_screen.refresh_requested.connect(self._refresh_history)
        self.database_screen.back_requested.connect(lambda: go(PAGE_MENU))

        self.history.history_loaded.connect(self.database_screen.show_rows)

    # ─────────────────────────────────────────────────────────────────────────
    # Process lifecycle
    # ─────────────────────────────────────────────────────────────────────────
    def start_process(self) -> None:
        target_mm = self.input_screen.target_thickness_mm()
        duration_s = self.input_screen.duration_s()
        if target_mm is None or duration_s is None:
            QMessageBox.warning(self, "Input Tidak Valid", "Target ketebalan dan waktu harus berupa angka.")
            return

        if self.input_screen.mode == "MANUAL":
            reply = QMessageBox.question(
                self, "Konfirmasi Proses",
                "Sistem berjalan di mode MANUAL.\nSensor ketebalan dinonaktifkan. Lanjutkan?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                self._begin(duration_s, baseline=(0.0, 0.0, 0.0))
            return

        calibration = CalibrationDialog(self.lasers, self)
        if calibration.exec_() != QDialog.Accepted:
            return
        reply = QMessageBox.question(
            self, "Start Proses Sesungguhnya",
            f"Target Ketebalan: {target_mm:g} mm.\nJarak stik awal berhasil disimpan.\n"
            "Silakan lapisi stik dengan gel.\nKlik Yes untuk memulai proses sesungguhnya.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            self._begin(duration_s, baseline=calibration.baseline)

    def _begin(self, duration_s: float, baseline: tuple[float, float, float]) -> None:
        shape, mode = self.input_screen.shape, self.input_screen.mode
        self.time_remaining_s = duration_s
        self.thickness = (0.0, 0.0, 0.0)
        self.response_time_ms = 0.0
        self.paused = False
        self.offsets.clear()
        self.drying.start()

        monitor = self.monitor_screen
        monitor.reset_readouts()

        self.imu.start()
        self.thermometer.start()

        if mode == "AUTO":
            self.controller = AutoController(shape, now_ms(), self.lasers, baseline, self.offsets)
            self.lasers.start()
        else:
            self.controller = ManualController(shape, now_ms(), self.offsets)
            monitor.build_manual_panel(shape, self.nudger)

        self.running = True
        monitor.set_status("AKTIF", style.GREEN)
        self.motors.start()

        self.stack.setCurrentIndex(PAGE_MONITOR)
        self.control_timer.start(config.CONTROL_PERIOD_MS)
        log.info("Process started: shape=%s mode=%s duration=%ss", shape, mode, duration_s)

    def stop_process(self) -> None:
        self.control_timer.stop()
        self.lasers.set_measurement_window(False)
        self.lasers.stop()
        self.imu.stop()
        self.thermometer.stop()

        if self.running:
            self._save_record()  # reads the IMU/thermometer's last values

        self.drying.finish()
        self._close_warning()

        if self._correction_dialog is not None:
            self._correction_dialog.close()

        if self.controller is not None:
            command = self.controller.stop_command()
            self.motors.send(command.pitch_steps, command.roll_speed, command.yaw_steps)
        self.motors.stop()  # flushes the stop command before closing the port

        self.controller = None
        self.running = False
        self.paused = False
        self.time_remaining_s = 0.0
        self.thickness = (0.0, 0.0, 0.0)
        self.monitor_screen.set_status("SIAP", style.RED)
        self.monitor_screen.reset_readouts()
        self.drying.reset()
        self._load_history()
        self.stack.setCurrentIndex(PAGE_MENU)
        log.info("Process stopped")

    def toggle_pause(self) -> None:
        if not self.running:
            return
        self.paused = not self.paused
        if self.paused:
            self.drying.pause()
            self.monitor_screen.pause_button.setText("RESUME")
            self.monitor_screen.set_status("JEDA")
        else:
            self.drying.resume()
            self.monitor_screen.pause_button.setText("PAUSE")
            self.monitor_screen.set_status("AKTIF")

    # ─────────────────────────────────────────────────────────────────────────
    # Timers
    # ─────────────────────────────────────────────────────────────────────────
    def _on_control_tick(self) -> None:
        if not self.running or self.controller is None:
            return
        self.monitor_screen.pitch_label.setText(f"{self.imu.get_pitch():.1f}°")
        self._apply_tick(self.controller.update(now_ms(), paused=self.paused))

    def _apply_tick(self, result: TickResult) -> None:
        if result.feedback is not None:
            self.thickness = result.feedback.thickness_mm
            self.monitor_screen.set_thickness(self.thickness)
            if result.feedback.valid:
                self.response_time_ms = result.feedback.response_time_ms
                self.monitor_screen.set_response_time(self.response_time_ms)
                self._save_record()

        if result.status is not None:
            self.monitor_screen.set_status(result.status)
        if result.imu_active is not None:
            self.imu.reading_active = result.imu_active
        if result.command is not None:
            c = result.command
            self.motors.send(c.pitch_steps, c.roll_speed, c.yaw_steps)
        if result.request_correction:
            self._open_correction_dialog()

    def _on_ui_tick(self) -> None:
        if not self.running:
            return
        if self.time_remaining_s <= 0:
            self.stop_process()
            return
        if self.paused:
            return

        self.time_remaining_s -= 1
        self.monitor_screen.set_countdown(self.time_remaining_s)

        temperature = round(self.thermometer.get_temperature(), 2)
        self.monitor_screen.temperature_label.setText(f"{temperature} °C")
        self.monitor_screen.graphs.append(self.thickness, temperature)

        action = self.drying.update(temperature)
        if action == DryingAction.SHOW_WARNING:
            self._show_warning()
        elif action == DryingAction.CLEAR_WARNING:
            self._close_warning()
        elif action == DryingAction.ABORT:
            self.stop_process()  # stop the motors first, then tell the operator
            QMessageBox.critical(
                self, "Intervensi Kritis",
                f"Suhu mencapai batas CRITICAL (< {config.TEMP_CRITICAL_C:g}°C)!\n"
                "Sistem dibatalkan (Aborted) ke mode FINISH.",
            )
            return

        if isinstance(self.controller, ManualController):
            self.monitor_screen.set_nudges_enabled(self.controller.staying)

    # ─────────────────────────────────────────────────────────────────────────
    # Dialogs & manual mode
    # ─────────────────────────────────────────────────────────────────────────
    def _open_correction_dialog(self) -> None:
        dialog = CorrectionDialog(self.nudger, self.lasers, self)
        dialog.finished.connect(self._on_correction_finished)
        dialog.show()
        self._correction_dialog = dialog

    def _on_correction_finished(self, _result: int) -> None:
        self._correction_dialog = None
        if isinstance(self.controller, AutoController):
            self.controller.end_correction()

    def _show_warning(self) -> None:
        if self._warning_box is not None:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Peringatan Suhu")
        box.setText(
            f"Suhu turun ke tingkat WARNING (< {config.TEMP_WARNING_C:g}°C)!\nProses drying tetap berjalan."
        )
        box.setStandardButtons(QMessageBox.Ok)
        box.setWindowModality(Qt.NonModal)  # do not block the HMI
        box.finished.connect(self._forget_warning)
        box.show()
        self._warning_box = box

    def _close_warning(self) -> None:
        if self._warning_box is not None:
            self._warning_box.accept()
        self._warning_box = None

    def _forget_warning(self, _result: int) -> None:
        self._warning_box = None

    def _on_preset_selected(self, preset: ManualPreset) -> None:
        if isinstance(self.controller, ManualController):
            self.controller.select_preset(preset)
            self.monitor_screen.set_status(f"TUNGGU {preset.cycle_time_s}s")

    def _on_normal_requested(self) -> None:
        if isinstance(self.controller, ManualController):
            self.controller.resume_tumbling()
            self.monitor_screen.set_status("NORMAL")

    # ─────────────────────────────────────────────────────────────────────────
    # Database
    # ─────────────────────────────────────────────────────────────────────────
    def _save_record(self) -> None:
        self.history.save(ProcessRecord(
            shape=self.input_screen.shape,
            mode=self.input_screen.mode,
            target_thickness_mm=self.input_screen.target_thickness_mm() or 0.0,
            target_time_s=self.input_screen.duration_s() or 0.0,
            thickness_1=self.thickness[0],
            thickness_2=self.thickness[1],
            thickness_3=self.thickness[2],
            final_temperature_c=self.thermometer.get_temperature(),
            pitch_deg=self.imu.get_pitch(),
            response_time_ms=self.response_time_ms,
        ))

    def _load_history(self) -> None:
        self.history.request_history(self.history_limit)

    def _load_more_history(self) -> None:
        self.history_limit += config.DB_HISTORY_PAGE_SIZE
        self._load_history()

    def _refresh_history(self) -> None:
        self.history_limit = config.DB_HISTORY_PAGE_SIZE
        self._load_history()

    def _open_database(self) -> None:
        self.stack.setCurrentIndex(PAGE_DATABASE)
        self._refresh_history()

    # ─────────────────────────────────────────────────────────────────────────
    # Qt events
    # ─────────────────────────────────────────────────────────────────────────
    def keyPressEvent(self, event):  # noqa: N802 (Qt API)
        if event.key() == Qt.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        elif event.key() == Qt.Key_Escape:
            self.showNormal() if self.isFullScreen() else self.close()

    def closeEvent(self, event):  # noqa: N802 (Qt API)
        self.stop_process()
        self.history.shutdown()
        event.accept()
