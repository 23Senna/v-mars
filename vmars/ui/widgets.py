"""Small reusable widgets for the touchscreen HMI."""

from __future__ import annotations

from typing import Callable

from PyQt5.QtCore import QObject, Qt, QTimer
from PyQt5.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vmars import config
from vmars.control.motion import MotionOffsets
from vmars.ui import style


def asset_pixmap(filename: str) -> QPixmap:
    return QPixmap(str(config.ASSETS_DIR / filename))


class NumericTableWidgetItem(QTableWidgetItem):
    """Sorts numerically when both cells are numbers, alphabetically otherwise."""

    def __lt__(self, other):
        if isinstance(other, QTableWidgetItem):
            try:
                return float(self.text()) < float(other.text())
            except ValueError:
                return self.text() < other.text()
        return super().__lt__(other)


class StickCanvas(QWidget):
    """Shows the picture of the selected stick shape."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.shape = "I"
        self.setMinimumSize(150, 100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_shape(self, shape: str) -> None:
        self.shape = shape
        self.update()

    def paintEvent(self, event):  # noqa: N802 (Qt API)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(style.CANVAS_BG)))
        painter.setPen(QPen(QColor(style.BORDER), 3))
        painter.drawRoundedRect(self.rect().adjusted(5, 5, -5, -5), 10, 10)

        pixmap = asset_pixmap(config.SHAPE_IMAGES.get(self.shape, config.SHAPE_IMAGES["I"]))
        if pixmap.isNull():
            painter.setPen(QColor("red"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Gambar tidak ditemukan")
            return

        pad = 15
        target = self.rect().adjusted(pad, pad, -pad, -pad)
        scaled = pixmap.scaled(target.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)


class NumpadDialog(QDialog):
    """On-screen numeric keypad (the panel has no physical keyboard)."""

    _KEYS = (
        ("7", 0, 0), ("8", 0, 1), ("9", 0, 2),
        ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
        ("1", 2, 0), ("2", 2, 1), ("3", 2, 2),
        (".", 3, 0), ("0", 3, 1), ("DEL", 3, 2),
    )

    def __init__(self, parent: QWidget | None = None, initial_value: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Input Angka")
        self.setModal(True)
        self.setStyleSheet(style.NUMPAD_STYLE)
        self.value = initial_value

        layout = QVBoxLayout(self)
        self.display = QLineEdit(self.value)
        self.display.setReadOnly(True)
        layout.addWidget(self.display)

        grid = QGridLayout()
        for key, row, col in self._KEYS:
            button = QPushButton(key)
            button.clicked.connect(lambda _checked, k=key: self._press(k))
            grid.addWidget(button, row, col)

        clear = QPushButton("CLEAR")
        clear.clicked.connect(lambda: self._press("CLEAR"))
        grid.addWidget(clear, 4, 0, 1, 2)

        ok = QPushButton("OK")
        ok.setStyleSheet(style.OK_BUTTON_STYLE)
        ok.clicked.connect(self.accept)
        grid.addWidget(ok, 4, 2, 1, 1)
        layout.addLayout(grid)

    def _press(self, key: str) -> None:
        if key == "CLEAR":
            self.value = ""
        elif key == "DEL":
            self.value = self.value[:-1]
        else:
            self.value += key
        self.display.setText(self.value)


class TouchNumberEdit(QLineEdit):
    """Line edit that opens :class:`NumpadDialog` when tapped."""

    def mousePressEvent(self, event):  # noqa: N802 (Qt API)
        super().mousePressEvent(event)
        dialog = NumpadDialog(self, self.text())
        if dialog.exec_() == QDialog.Accepted:
            self.setText(dialog.value)

    def float_value(self, default: float | None = None) -> float | None:
        try:
            return float(self.text())
        except ValueError:
            return default


class MotionNudger(QObject):
    """Applies operator nudges to :class:`MotionOffsets`.

    Pitch/yaw nudges are permanent offsets. A roll nudge runs the roll motor
    for 500 ms at a speed chosen so it turns exactly the requested angle.
    """

    def __init__(self, offsets: MotionOffsets, parent: QObject | None = None):
        super().__init__(parent)
        self.offsets = offsets
        self._roll_timer = QTimer(self)
        self._roll_timer.setSingleShot(True)
        self._roll_timer.timeout.connect(self._stop_roll)

    def nudge_pitch(self, degrees: float) -> None:
        self.offsets.pitch_deg += degrees

    def nudge_yaw(self, degrees: float) -> None:
        self.offsets.yaw_deg += degrees

    def nudge_roll(self, degrees: float) -> None:
        duration_s = config.NUDGE_ROLL_DURATION_MS / 1000.0
        self.offsets.roll_speed = degrees * config.STEPS_PER_DEGREE / duration_s
        self._roll_timer.start(config.NUDGE_ROLL_DURATION_MS)

    def _stop_roll(self) -> None:
        self.offsets.roll_speed = 0.0


NUDGE_STEPS = (("<< -5°", -5.0), ("< -1°", -1.0), ("> +1°", 1.0), (">> +5°", 5.0))


def make_nudge_buttons(
    on_nudge: Callable[[float], None], button_style: str | None = None
) -> list[QPushButton]:
    """The four ``-5 / -1 / +1 / +5`` buttons for one axis."""
    buttons = []
    for text, value in NUDGE_STEPS:
        button = QPushButton(text)
        if button_style:
            button.setStyleSheet(button_style)
        button.clicked.connect(lambda _checked, v=value: on_nudge(v))
        buttons.append(button)
    return buttons


def hbox(*widgets: QWidget) -> QHBoxLayout:
    layout = QHBoxLayout()
    for widget in widgets:
        layout.addWidget(widget)
    return layout
