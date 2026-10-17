from vmars.hardware.laser import LaserSensorArray, LaserSensorWorker


def test_worker_without_port_stops_and_joins_cleanly():
    """Regression: an attribute named ``_stop`` shadowed ``Thread._stop`` and
    made ``join()`` raise TypeError on Python <= 3.12."""
    worker = LaserSensorWorker("/dev/does-not-exist", "S1")
    worker.start()
    worker.stop()
    worker.join(timeout=2.0)
    assert not worker.is_alive()
    assert not worker.is_connected
    assert worker.has_valid_reading()  # a missing sensor never blocks the process


def test_array_start_stop_without_hardware(monkeypatch):
    monkeypatch.setattr("vmars.config.JRT_S1_PORT", "/dev/does-not-exist-1")
    monkeypatch.setattr("vmars.config.JRT_S2_PORT", "/dev/does-not-exist-2")
    array = LaserSensorArray()
    array.start()
    array.stop()
    assert array.connected() == (False, False, False)
