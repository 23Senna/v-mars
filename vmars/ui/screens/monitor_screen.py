"""Live monitoring: state, timer, pitch, temperature, thickness and plots.

In MANUAL mode the thickness widgets are hidden and a control panel with the
shape presets and pitch/roll/yaw nudge buttons is shown instead.
"""

from __future__ import annotations

from collections import deque

import pyqtgraph as pg
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from vmars import config
from vmars.control.sequences import MANUAL_PRESETS
from vmars.ui import style
from vmars.ui.widgets import MotionNudger, make_nudge_buttons


def _info_box(caption: str, value: QLabel) -> QFrame:
    frame = QFrame()
    frame.setObjectName("infoBox")
    row = QHBoxLayout(frame)
    row.addWidget(QLabel(caption))
    row.addStretch()
    row.addWidget(value)
    return frame


def _plot(title: str) -> pg.PlotWidget:
    plot = pg.PlotWidget()
    plot.setTitle(title, color=style.RED, size="12pt", bold=True)
    plot.setBackground(style.WHITE)
    plot.showGrid(x=True, y=True, alpha=0.5)
    for axis in ("left", "bottom"):
        plot.getAxis(axis).setPen(pg.mkPen(color=style.BORDER, width=1))
        plot.getAxis(axis).setTextPen(style.INK)
    plot.setLabel("bottom", "Waktu", color=style.INK, units="s")
    return plot


class LiveGraphs:
    """Rolling 60-sample history for the thickness and temperature plots."""

    def __init__(self, thickness_plot: pg.PlotWidget, temperature_plot: pg.PlotWidget):
        pens = (style.RED, style.ORANGE, style.INK)
        self._thickness_curves = [
            thickness_plot.plot(pen=pg.mkPen(color, width=3), name=f"S{i}")
            for i, color in enumerate(pens, start=1)
        ]
        self._temperature_curve = temperature_plot.plot(pen=pg.mkPen(style.GREEN, width=3))
        self.clear()

    def clear(self) -> None:
        n = config.GRAPH_WINDOW_POINTS
        self._time: deque[float] = deque(maxlen=n)
        self._thickness = [deque(maxlen=n) for _ in range(3)]
        self._temperature: deque[float] = deque(maxlen=n)
        self._elapsed = 0
        self._redraw()

    def append(self, thickness: tuple[float, float, float], temperature: float) -> None:
        self._time.append(self._elapsed)
        for series, value in zip(self._thickness, thickness):
            series.append(value)
        self._temperature.append(temperature)
        self._elapsed += 1
        self._redraw()

    def _redraw(self) -> None:
        x = list(self._time)
        for curve, series in zip(self._thickness_curves, self._thickness):
            curve.setData(x, list(series))
        self._temperature_curve.setData(x, list(self._temperature))


class MonitorScreen(QWidget):
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    back_requested = pyqtSignal()
    preset_selected = pyqtSignal(object)  # ManualPreset
    normal_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 50)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(self._build_status_panel(), 5)
        top.addWidget(self._build_plot_panel(), 5)

        body = QVBoxLayout()
        body.setSpacing(10)
        body.addLayout(top, 60)

        self.manual_group = QGroupBox("KONTROL MANUAL")
        self.manual_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.manual_group.setStyleSheet(style.MANUAL_GROUP_STYLE)
        self._manual_layout = QVBoxLayout(self.manual_group)
        self._manual_panel: QWidget | None = None
        self.nudge_buttons: list[QPushButton] = []
        self.manual_group.setVisible(False)
        body.addWidget(self.manual_group, 40)

        layout.addLayout(body)

    # ── layout ───────────────────────────────────────────────────────────────
    def _build_status_panel(self) -> QGroupBox:
        group = QGroupBox("MONITORING")
        group.setMinimumWidth(350)
        group.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        outer = QVBoxLayout(group)
        outer.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")
        scroll.setSizeAdjustPolicy(QScrollArea.AdjustToContents)
        scroll.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Expanding)

        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        content.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        rows = QVBoxLayout(content)
        rows.setSpacing(4)

        # State + countdown
        state_frame = QFrame()
        state_frame.setObjectName("infoBox")
        state_row = QHBoxLayout(state_frame)
        self.status_label = QLabel("SIAP")
        self.status_label.setStyleSheet(style.big_value(style.RED))
        self.timer_label = QLabel("00:00")
        self.timer_label.setStyleSheet(style.big_value(style.ORANGE, 18))
        state_row.addWidget(QLabel("STATE:"))
        state_row.addWidget(self.status_label)
        state_row.addStretch()
        state_row.addWidget(QLabel("TIMER:"))
        state_row.addWidget(self.timer_label)
        rows.addWidget(state_frame)

        # Pitch + temperature
        self.pitch_label = QLabel("0.0°")
        self.pitch_label.setStyleSheet(style.big_value(style.ORANGE))
        self.temperature_label = QLabel("0.0 °C")
        self.temperature_label.setStyleSheet(style.big_value(style.GREEN))
        pitch_temp = QHBoxLayout()
        pitch_temp.setSpacing(4)
        pitch_temp.addWidget(_info_box("Pitch:", self.pitch_label))
        pitch_temp.addWidget(_info_box("Suhu:", self.temperature_label))
        rows.addLayout(pitch_temp)

        # Response time
        self.response_label = QLabel("– ms")
        self.response_label.setStyleSheet(style.big_value(style.INK, 14))
        self.response_frame = _info_box("Response Time:", self.response_label)
        rows.addWidget(self.response_frame)

        # Thickness per measuring point
        self.thickness_labels: list[QLabel] = []
        self.thickness_frames: list[QFrame] = []
        for i in (1, 2, 3):
            value = QLabel("0 mm")
            value.setStyleSheet(style.big_value(style.RED))
            frame = _info_box(f"Tebal Titik S{i}", value)
            rows.addWidget(frame)
            self.thickness_labels.append(value)
            self.thickness_frames.append(frame)

        rows.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        controls = QHBoxLayout()
        stop = QPushButton("STOP")
        stop.setObjectName("btnStop")
        stop.clicked.connect(self.stop_requested.emit)
        self.pause_button = QPushButton("PAUSE")
        self.pause_button.setObjectName("btnReset")
        self.pause_button.clicked.connect(self.pause_requested.emit)
        controls.addWidget(stop)
        controls.addWidget(self.pause_button)
        outer.addLayout(controls)

        back = QPushButton("MAIN MENU")
        back.clicked.connect(self.back_requested.emit)
        outer.addWidget(back)
        return group

    def _build_plot_panel(self) -> QWidget:
        pg.setConfigOptions(antialias=True)
        self.thickness_plot = _plot("Ketebalan Hydrogel (mm)")
        legend = self.thickness_plot.addLegend(offset=(10, 10))
        legend.setBrush(pg.mkBrush(color=(255, 255, 255, 210)))
        legend.setPen(pg.mkPen(color=style.BORDER))

        self.temperature_plot = _plot("Suhu Lingkungan (°C)")
        self.temperature_plot.showAxis("bottom")
        self.graphs = LiveGraphs(self.thickness_plot, self.temperature_plot)

        panel = QVBoxLayout()
        panel.setSpacing(6)
        panel.addWidget(self.thickness_plot)
        panel.addWidget(self.temperature_plot)

        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        widget.setLayout(panel)
        return widget

    # ── mode-dependent pieces ────────────────────────────────────────────────
    def set_mode(self, mode: str) -> None:
        is_auto = mode == "AUTO"
        for frame in self.thickness_frames:
            frame.setVisible(is_auto)
        self.response_frame.setVisible(is_auto)
        self.thickness_plot.setVisible(is_auto)
        self.manual_group.setVisible(not is_auto)

    def build_manual_panel(self, shape: str, nudger: MotionNudger) -> None:
        """(Re)create the preset and nudge buttons for ``shape``."""
        if self._manual_panel is not None:
            self._manual_panel.deleteLater()

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)

        # Presets (first cell is NORMAL, then 4 per row)
        width, height = style.PRESET_BUTTON_SIZE.get(shape, ("90px", "40px"))
        presets = QGridLayout()
        normal = QPushButton("NORMAL")
        normal.setObjectName("btnReset")
        normal.setStyleSheet(f"min-width: {width}; min-height: {height};")
        normal.clicked.connect(self.normal_requested.emit)
        presets.addWidget(normal, 0, 0)
        for index, preset in enumerate(MANUAL_PRESETS.get(shape, ()), start=1):
            button = QPushButton(preset.label)
            button.setObjectName("btnShape")
            button.setStyleSheet(style.preset_button_style(width, height))
            button.clicked.connect(lambda _checked, p=preset: self.preset_selected.emit(p))
            presets.addWidget(button, index // 4, index % 4)
        panel_layout.addLayout(presets)

        # Nudges (only enabled while a preset pose is being held)
        nudges = QGridLayout()
        nudges.setSpacing(10)
        self.nudge_buttons = []
        for row, (axis, handler) in enumerate((
            ("Pitch:", nudger.nudge_pitch),
            ("Roll:", nudger.nudge_roll),
            ("Yaw:", nudger.nudge_yaw),
        )):
            caption = QLabel(axis)
            caption.setStyleSheet(f"font-weight: bold; color: {style.RED};")
            nudges.addWidget(caption, row, 0)
            for col, button in enumerate(make_nudge_buttons(handler, style.NUDGE_BUTTON_STYLE), start=1):
                button.setEnabled(False)
                nudges.addWidget(button, row, col)
                self.nudge_buttons.append(button)
        nudges.setColumnStretch(5, 1)
        panel_layout.addLayout(nudges)

        self._manual_layout.addWidget(panel)
        self._manual_panel = panel

    def set_nudges_enabled(self, enabled: bool) -> None:
        for button in self.nudge_buttons:
            button.setEnabled(enabled)

    # ── value updates ────────────────────────────────────────────────────────
    def set_status(self, text: str, color: str | None = None) -> None:
        self.status_label.setText(text)
        if color:
            self.status_label.setStyleSheet(f"color: {color};")

    def set_countdown(self, seconds: float) -> None:
        minutes, secs = divmod(int(seconds), 60)
        self.timer_label.setText(f"{minutes:02d}:{secs:02d}")

    def set_thickness(self, thickness: tuple[float, float, float]) -> None:
        for label, value in zip(self.thickness_labels, thickness):
            label.setText(f"{value:.1f} mm")

    def set_response_time(self, ms: float | None) -> None:
        self.response_label.setText("– ms" if ms is None else f"{ms:.1f} ms")

    def reset_readouts(self) -> None:
        self.timer_label.setText("00:00")
        self.pitch_label.setText("0.0°")
        self.set_response_time(None)
        self.set_thickness((0.0, 0.0, 0.0))
        self.graphs.clear()
        self.pause_button.setText("PAUSE")

