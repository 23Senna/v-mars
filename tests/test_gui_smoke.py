"""Starts the real MainWindow off-screen with no hardware attached."""

import pytest

pytest.importorskip("PyQt5")
pytest.importorskip("pyqtgraph")
pytest.importorskip("psycopg2")

from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from vmars.control import AutoController, ManualController  # noqa: E402
from vmars.control.sequences import MANUAL_PRESETS  # noqa: E402
from vmars.ui import main_window  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: QMessageBox.Ok)
    monkeypatch.setattr(main_window.CalibrationDialog, "exec_", lambda self: QDialog.Accepted)
    win = main_window.MainWindow()
    # No SHT31 here: it would read 0 °C and the drying monitor would abort.
    monkeypatch.setattr(win.thermometer, "get_temperature", lambda: 25.0)
    yield win
    win.close()


def test_manual_run(window):
    window.input_screen.set_shape("Y")
    window.input_screen.set_mode("MANUAL")
    window.start_process()
    assert window.running and isinstance(window.controller, ManualController)

    window._on_preset_selected(MANUAL_PRESETS["Y"][1])
    for _ in range(20):
        window._on_control_tick()
    window._on_ui_tick()
    window.toggle_pause()
    window._on_control_tick()
    window.toggle_pause()
    window.stop_process()
    assert not window.running


def test_auto_run_without_sensors(window):
    window.input_screen.set_shape("T")
    window.input_screen.set_mode("AUTO")
    window.start_process()
    assert isinstance(window.controller, AutoController)
    for _ in range(5):
        window._on_control_tick()
    window.stop_process()
    assert window.controller is None


def test_cold_environment_aborts(window, monkeypatch):
    window.input_screen.set_mode("MANUAL")
    window.start_process()
    monkeypatch.setattr(window.thermometer, "get_temperature", lambda: 18.0)
    window._on_ui_tick()
    assert not window.running
