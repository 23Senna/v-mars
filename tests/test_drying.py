from vmars.control.drying import DryingAction, DryingMonitor, DryingState


def started():
    monitor = DryingMonitor(warning_c=24.0, critical_c=20.0)
    monitor.start()
    return monitor


def test_normal_temperature_does_nothing():
    monitor = started()
    assert monitor.update(26.0) == DryingAction.NONE
    assert monitor.state == DryingState.NORMAL


def test_warning_then_recovery():
    monitor = started()
    assert monitor.update(23.5) == DryingAction.SHOW_WARNING
    assert monitor.update(23.0) == DryingAction.NONE
    assert monitor.update(24.0) == DryingAction.CLEAR_WARNING
    assert monitor.state == DryingState.NORMAL


def test_warning_then_critical_aborts():
    monitor = started()
    monitor.update(22.0)
    assert monitor.update(19.9) == DryingAction.ABORT
    assert monitor.state == DryingState.INTERVENTION


def test_direct_drop_to_critical_aborts():
    assert started().update(15.0) == DryingAction.ABORT


def test_paused_monitor_ignores_samples():
    monitor = started()
    monitor.pause()
    assert monitor.update(10.0) == DryingAction.NONE
    monitor.resume()
    assert monitor.update(10.0) == DryingAction.ABORT
