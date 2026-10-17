from vmars import config
from vmars.control import ManualController
from vmars.control.sequences import MANUAL_PRESETS

SPD = config.STEPS_PER_DEGREE


def run(ctrl, clock, seconds):
    results = []
    target = clock.now + seconds * 1000.0
    while clock.now < target:
        results.append(ctrl.update(clock.advance()))
    return results


def test_tumbles_at_45_deg_per_second(clock):
    ctrl = ManualController("Y", clock.now)
    result = run(ctrl, clock, 2.0)[-1]
    assert result.command.pitch_steps == int(90 * SPD)
    assert result.command.yaw_steps == int(90 * SPD)
    assert result.status == "NORMAL"


def test_preset_locks_pose_for_30_seconds(clock):
    ctrl = ManualController("I", clock.now)
    run(ctrl, clock, 9.0)  # somewhere in the 2nd cycle
    preset = MANUAL_PRESETS["I"][1]  # STAY 180° at cycle time 8 s → 4 s in the fast cycle
    ctrl.select_preset(preset)

    results = run(ctrl, clock, 5.0)
    assert ctrl.staying
    held = [r for r in results if r.status.startswith("TAHAN")]
    assert held
    pitch_deg = held[-1].command.pitch_steps / SPD
    assert round(pitch_deg) % 360 == 180

    run(ctrl, clock, config.MANUAL_STAY_DURATION_S)
    assert not ctrl.staying


def test_resume_cancels_waiting(clock):
    ctrl = ManualController("T", clock.now)
    ctrl.select_preset(MANUAL_PRESETS["T"][0])
    ctrl.resume_tumbling()
    assert not ctrl.waiting and not ctrl.staying
