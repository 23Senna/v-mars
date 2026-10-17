from vmars import config
from vmars.control import AutoController, MotionOffsets

SPD = config.STEPS_PER_DEGREE
BASELINE = (100.0, 120.0, 140.0)


def make(shape, clock, sensors, offsets=None):
    return AutoController(shape, clock.now, sensors, BASELINE, offsets or MotionOffsets())


def run_until(ctrl, clock, seconds, paused=False):
    results = []
    target = clock.now + seconds * 1000.0
    while clock.now < target:
        results.append(ctrl.update(clock.advance(), paused=paused))
    return results


def test_initial_phase_ramps_pitch_and_yaw(clock, fake_sensors_cls):
    ctrl = make("T", clock, fake_sensors_cls(clock))
    result = run_until(ctrl, clock, 10.0)[-1]
    assert result.command.pitch_steps == int(22.5 * 10 * SPD)
    assert result.command.yaw_steps == int(22.5 * 10 * SPD)
    assert result.command.roll_speed == config.ROLL_SPEED_TUMBLING
    assert result.status.startswith("AWAL")


def test_i_shape_never_yaws(clock, fake_sensors_cls):
    ctrl = make("I", clock, fake_sensors_cls(clock))
    assert all(r.command.yaw_steps == 0 for r in run_until(ctrl, clock, 39.0))


def test_roll_stops_before_measuring(clock, fake_sensors_cls):
    ctrl = make("I", clock, fake_sensors_cls(clock))
    results = run_until(ctrl, clock, 39.9)
    assert results[-1].status.startswith("STABIL")
    assert results[-1].command.roll_speed == 0.0


def test_measurement_pose_and_early_exit(clock, fake_sensors_cls):
    sensors = fake_sensors_cls(clock, valid_after_ms=500.0)
    ctrl = make("3D", clock, sensors)
    results = run_until(ctrl, clock, 40.0)
    measure = results[-1]
    assert measure.status.startswith("UKUR")
    assert measure.command.pitch_steps == int(900 * SPD)
    assert measure.command.yaw_steps == int(720 * SPD)

    # sensors were reset at t=38 s and are valid 0.5 s later → UKUR ends early
    feedback_tick = ctrl.update(clock.advance())
    assert feedback_tick.feedback is not None and feedback_tick.feedback.valid


def test_feedback_tick_holds_measuring_pose(clock, fake_sensors_cls):
    """Regression: the original sent pitch=0/yaw=0 on this tick."""
    ctrl = make("3D", clock, fake_sensors_cls(clock, valid_after_ms=0.0))
    results = run_until(ctrl, clock, 41.0)
    feedback = next(r for r in results if r.feedback is not None)
    assert feedback.command.pitch_steps == int(900 * SPD)
    assert feedback.command.yaw_steps == int(720 * SPD)


def test_correction_profile_i_b(clock, fake_sensors_cls):
    # S1 thicker than S2 → I-B: go to 0°, hold until 47 s, then continue.
    sensors = fake_sensors_cls(clock, distances=(97.0, 119.0, 0.0), valid_after_ms=0.0,
                               connected=(True, True, False))
    ctrl = make("I", clock, sensors)
    results = run_until(ctrl, clock, 60.0)
    assert ctrl.condition == "I-B"
    statuses = [r.status for r in results if r.status]
    assert "KE 0°" in statuses
    assert any(s.startswith("SET 0°") for s in statuses)
    hold = next(r for r in results if r.status and r.status.startswith("SET 0°"))
    assert hold.command.pitch_steps == int((900 + 180) * SPD)


def test_timeout_requests_correction_and_freezes(clock, fake_sensors_cls):
    sensors = fake_sensors_cls(clock, valid_after_ms=60_000.0)
    offsets = MotionOffsets()
    ctrl = make("I", clock, sensors, offsets)
    results = run_until(ctrl, clock, 46.0)
    assert any(r.request_correction for r in results)
    assert ctrl.correcting

    start_before = ctrl.start_ms
    offsets.pitch_deg = 5.0
    result = ctrl.update(clock.advance())
    assert ctrl.start_ms == start_before + 100.0  # process clock frozen
    assert result.command.pitch_steps == int(905 * SPD)

    ctrl.end_correction()
    assert not ctrl.correcting


def test_invalid_measurement_repeats_ukur(clock, fake_sensors_cls):
    # S1 distance equals the baseline → 0 mm thickness → invalid
    sensors = fake_sensors_cls(clock, distances=(100.0, 117.0, 136.0), valid_after_ms=0.0)
    ctrl = make("T", clock, sensors)
    results = run_until(ctrl, clock, 41.0)
    invalid = [r.feedback for r in results if r.feedback is not None]
    assert invalid and not any(f.valid for f in invalid)
    assert not ctrl.has_calculated


def test_pause_freezes_process_clock(clock, fake_sensors_cls):
    ctrl = make("T", clock, fake_sensors_cls(clock))
    run_until(ctrl, clock, 5.0)
    last = ctrl.last_command
    start = ctrl.start_ms
    paused = run_until(ctrl, clock, 3.0, paused=True)
    assert ctrl.start_ms == start + 3000.0
    assert all(r.command == last.stopped() for r in paused)
