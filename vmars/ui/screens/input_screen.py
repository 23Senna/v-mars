"""Operator input: stick shape, operating mode, dimensions, target, duration."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from vmars import config
from vmars.ui.widgets import StickCanvas, TouchNumberEdit


class InputScreen(QWidget):
    shape_changed = pyqtSignal(str)
    mode_changed = pyqtSignal(str)
    start_requested = pyqtSignal()
    back_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 50)

        group = QGroupBox("OPERATOR INPUT")
        columns = QHBoxLayout(group)
        columns.setSpacing(10)
        columns.addLayout(self._build_shape_column(), 1)
        columns.addLayout(self._build_parameter_column(), 1)
        layout.addWidget(group)

        self.set_shape("I")
        self.set_mode("AUTO")

    # ── layout ───────────────────────────────────────────────────────────────
    def _build_shape_column(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(5)
        column.addWidget(QLabel("<b>Pilih Bentuk Stik:</b>"))

        row = QHBoxLayout()
        self.shape_buttons: dict[str, QPushButton] = {}
        for shape in config.SHAPES:
            button = QPushButton(shape)
            button.setObjectName("btnShape")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked, s=shape: self.set_shape(s))
            row.addWidget(button)
            self.shape_buttons[shape] = button
        column.addLayout(row)

        self.canvas = StickCanvas()
        column.addWidget(self.canvas)
        return column

    def _build_parameter_column(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(5)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }")

        content = QWidget()
        # ".QWidget" (leading dot) so the rule is not inherited by the buttons.
        content.setStyleSheet(".QWidget { background-color: transparent; }")
        form = QVBoxLayout(content)
        form.setSpacing(5)

        form.addWidget(QLabel("<b>Pilih Mode Operasi:</b>"))
        mode_row = QHBoxLayout()
        self.mode_buttons: dict[str, QPushButton] = {}
        for mode, text in (("AUTO", "AUTO"), ("MANUAL", "MANUAL")):
            button = QPushButton(text)
            button.setObjectName("btnMode")
            button.setCheckable(True)
            button.setMinimumHeight(40)
            button.clicked.connect(lambda _checked, m=mode: self.set_mode(m))
            mode_row.addWidget(button)
            self.mode_buttons[mode] = button
        form.addLayout(mode_row)
        form.addSpacing(10)

        self.branch_labels = [QLabel(f"Cabang {i} (mm):") for i in (1, 2, 3)]
        self.branch_inputs = [TouchNumberEdit(v) for v in ("50.0", "30.0", "20.0")]
        for label, edit in zip(self.branch_labels, self.branch_inputs):
            form.addWidget(label)
            form.addWidget(edit)

        form.addSpacing(5)
        self.thickness_input = TouchNumberEdit("2")
        self.time_input = TouchNumberEdit("60")
        form.addWidget(QLabel("Target Ketebalan (mm):"))
        form.addWidget(self.thickness_input)
        form.addWidget(QLabel("Waktu (detik):"))
        form.addWidget(self.time_input)
        form.addStretch()

        scroll.setWidget(content)
        column.addWidget(scroll)

        start = QPushButton("START PROCESS")
        start.setObjectName("btnStart")
        start.clicked.connect(self.start_requested.emit)
        column.addWidget(start)

        back = QPushButton("MAIN MENU")
        back.clicked.connect(self.back_requested.emit)
        column.addWidget(back)
        return column

    # ── state ────────────────────────────────────────────────────────────────
    def set_shape(self, shape: str) -> None:
        self.shape = shape
        self.canvas.set_shape(shape)
        for name, button in self.shape_buttons.items():
            button.setChecked(name == shape)
        branches = config.SHAPE_BRANCH_COUNT[shape]
        for i, (label, edit) in enumerate(zip(self.branch_labels, self.branch_inputs)):
            label.setVisible(i < branches)
            edit.setVisible(i < branches)
        self.shape_changed.emit(shape)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        for name, button in self.mode_buttons.items():
            button.setChecked(name == mode)
        self.mode_changed.emit(mode)

    def target_thickness_mm(self) -> float | None:
        return self.thickness_input.float_value()

    def duration_s(self) -> float | None:
        return self.time_input.float_value()
