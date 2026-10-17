"""Pop-up dialogs used during a process."""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from vmars.hardware.laser import LaserSensorArray
from vmars.ui import style
from vmars.ui.widgets import MotionNudger, make_nudge_buttons

_POLL_MS = 500


class CorrectionDialog(QDialog):
    """Shown when the lasers did not get a valid reading in time.

    The operator nudges pitch/roll/yaw until the sensors see the stick; the
    dialog closes itself as soon as all readings are valid.
    """

    def __init__(self, nudger: MotionNudger, sensors: LaserSensorArray, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Koreksi Manual Sensor (Anomali)")
        self.setModal(True)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet(style.CORRECTION_DIALOG_STYLE)
        self._sensors = sensors

        layout = QVBoxLayout(self)
        intro = QLabel("Pembacaan sensor belum valid (>1000mm).\nLakukan penyesuaian posisi manual:")
        intro.setAlignment(Qt.AlignCenter)
        layout.addWidget(intro)

        for axis, handler in (
            ("Pitch:", nudger.nudge_pitch),
            ("Roll:", nudger.nudge_roll),
            ("Yaw:", nudger.nudge_yaw),
        ):
            layout.addWidget(QLabel(axis))
            row = QHBoxLayout()
            for button in make_nudge_buttons(handler):
                row.addWidget(button)
            layout.addLayout(row)

        ok = QPushButton("OK (Lanjut)")
        ok.setStyleSheet(style.OK_BUTTON_STYLE + " margin-top: 10px;")
        ok.clicked.connect(self.accept)
        layout.addWidget(ok)

        self._poll = QTimer(self)
        self._poll.timeout.connect(self._close_when_valid)
        self._poll.start(_POLL_MS)

    def _close_when_valid(self) -> None:
        if self._sensors.all_valid():
            self.accept()

    def done(self, result: int) -> None:
        self._poll.stop()
        super().done(result)


class CalibrationDialog(QDialog):
    """Measures the bare-stick distance (baseline) before gel is applied."""

    def __init__(self, sensors: LaserSensorArray, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Kalibrasi Jarak Stik Awal")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setStyleSheet(style.CALIBRATION_DIALOG_STYLE)
        self._sensors = sensors
        self.baseline: tuple[float, float, float] = (0.0, 0.0, 0.0)

        layout = QVBoxLayout(self)
        self._info = QLabel()
        self._info.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._info)

        self._readouts = [QLabel(f"S{i}: - mm") for i in (1, 2, 3)]
        for label in self._readouts:
            layout.addWidget(label)

        buttons = QHBoxLayout()
        retry = QPushButton("ULANG")
        retry.clicked.connect(self.start_measuring)
        self._ok = QPushButton("OK (SIMPAN)")
        self._ok.setStyleSheet(style.OK_BUTTON_STYLE)
        self._ok.clicked.connect(self.accept)
        buttons.addWidget(retry)
        buttons.addWidget(self._ok)
        layout.addLayout(buttons)

        self._poll = QTimer(self)
        self._poll.timeout.connect(self._check_readings)
        self.start_measuring()

    def start_measuring(self) -> None:
        self._info.setText("Mengukur jarak ke stik...\nLaser menyala...")
        self._ok.setEnabled(False)
        for i, label in enumerate(self._readouts, start=1):
            label.setText(f"S{i}: Mengukur...")

        self._sensors.start()
        self._sensors.reset()
        self._sensors.set_measurement_window(True)
        self._poll.start(_POLL_MS)

    def _check_readings(self) -> None:
        if not self._sensors.all_valid():
            return
        self._poll.stop()
        self._sensors.set_measurement_window(False)

        self.baseline = self._sensors.best_distances()
        for i, (label, value) in enumerate(zip(self._readouts, self.baseline), start=1):
            label.setText(f"S{i}: {value} mm")
        self._info.setText("Pengukuran selesai.\nJarak berhasil didapatkan.")
        self._ok.setEnabled(True)
        self._sensors.stop()

    def done(self, result: int) -> None:
        # Covers OK, Esc and the window close button: never leave a laser on.
        self._poll.stop()
        self._sensors.set_measurement_window(False)
        self._sensors.stop()
        super().done(result)

    def closeEvent(self, event):  # noqa: N802 (Qt API)
        self._poll.stop()
        self._sensors.set_measurement_window(False)
        self._sensors.stop()
        event.accept()
