import pytest

from vmars.control.feedback import compute_thickness, decide_condition, has_invalid_point
from vmars.control.sequences import CORRECTION_PROFILES


def test_thickness_is_baseline_minus_distance():
    assert compute_thickness((100, 120, 140), (98, 117.5, 141)) == (2.0, 2.5, 0.0)


def test_missing_reading_or_baseline_gives_zero():
    assert compute_thickness((0, 120, 140), (98, 0, 139)) == (0.0, 0.0, 1.0)


def test_zero_thickness_on_connected_sensor_is_invalid():
    assert has_invalid_point((2.0, 0.0, 1.0), (True, True, True))
    assert not has_invalid_point((2.0, 0.0, 0.0), (True, False, False))


@pytest.mark.parametrize("thickness, expected", [
    ((1.0, 2.0, 0.0), "I-A"),
    ((2.0, 2.0, 0.0), "I-A"),
    ((3.0, 2.0, 0.0), "I-B"),
])
def test_i_shape(thickness, expected):
    assert decide_condition("I", thickness)[0] == expected


@pytest.mark.parametrize("thickness, expected", [
    ((1.0, 2.0, 3.0), "Y-C"),
    ((3.0, 1.0, 2.0), "Y-D-S2"),
    ((3.0, 2.0, 1.0), "Y-D-S3"),
    ((2.0, 1.0, 3.0), "Y-E-S2"),
    ((2.0, 3.0, 1.0), "Y-E-S3"),
])
def test_y_shape(thickness, expected):
    # Regression: the original code referenced an undefined ``max_val`` here.
    assert decide_condition("Y", thickness)[0] == expected


@pytest.mark.parametrize("thickness, expected", [
    ((1.0, 3.0, 2.0), "T-A-S2"),
    ((1.0, 2.0, 3.0), "T-A-S3"),
    ((3.0, 1.0, 2.0), "T-B-S2"),
    ((3.0, 2.0, 1.0), "T-B-S3"),
])
def test_t_shape(thickness, expected):
    assert decide_condition("T", thickness)[0] == expected


@pytest.mark.parametrize("thickness, expected", [
    ((1.0, 2.0, 3.0), "3D-A"),
    ((2.0, 1.0, 3.0), "3D-B"),
    ((2.0, 3.0, 1.0), "3D-C"),
])
def test_3d_shape(thickness, expected):
    assert decide_condition("3D", thickness)[0] == expected


@pytest.mark.parametrize("shape", ["I", "T", "Y", "3D"])
def test_every_decision_has_a_profile(shape):
    samples = [(a, b, c) for a in (1, 2, 3) for b in (1, 2, 3) for c in (1, 2, 3)]
    for thickness in samples:
        code, _ = decide_condition(shape, thickness)
        assert code in CORRECTION_PROFILES
