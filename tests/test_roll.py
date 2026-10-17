from vmars.control.roll import RollPositionTracker

REV = 2832.0


def test_keeps_rolling_until_full_revolution():
    tracker = RollPositionTracker(REV, 600.0)
    for _ in range(10):  # 1 s at 600 steps/s → 600 steps into a revolution
        assert tracker.update(600.0, 0.1) == 600.0

    ticks = 0
    while tracker.update(0.0, 0.1) != 0.0:
        assert tracker.finishing
        ticks += 1
        assert ticks < 100
    assert not tracker.finishing
    assert tracker.position_steps % REV == 0


def test_stops_immediately_when_aligned():
    tracker = RollPositionTracker(REV, 600.0)
    assert tracker.update(0.0, 0.1) == 0.0
    assert not tracker.finishing
