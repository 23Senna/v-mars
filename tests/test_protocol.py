import pytest

from vmars.hardware.protocol import (
    format_motor_command,
    parse_jrt_frame,
    sht31_raw_to_celsius,
    to_int16,
    wrap_degrees,
)


def test_motor_command_format():
    assert format_motor_command(7080.9, 600, -354.2) == "7080,600.0,-354\n"


def test_parse_jrt_frame():
    body = bytes([0, 0, 0, 0, 0, 0x00, 0x00, 0x01, 0x2C, 0x00, 0x7B, 0xFF])
    reading = parse_jrt_frame(body)
    assert reading.distance_mm == 300
    assert reading.quality == 123


def test_parse_jrt_frame_rejects_short_body():
    with pytest.raises(ValueError):
        parse_jrt_frame(b"\x00" * 11)


@pytest.mark.parametrize("high, low, expected", [
    (0x00, 0x01, 1), (0x7F, 0xFF, 32767), (0x80, 0x00, -32768), (0xFF, 0xFF, -1),
])
def test_to_int16(high, low, expected):
    assert to_int16(high, low) == expected


def test_sht31_conversion():
    assert sht31_raw_to_celsius(0) == pytest.approx(-45.0)
    assert sht31_raw_to_celsius(65535) == pytest.approx(130.0)


@pytest.mark.parametrize("angle, expected", [(0, 0), (190, -170), (360, 0), (-190, 170), (180, -180)])
def test_wrap_degrees(angle, expected):
    assert wrap_degrees(angle) == pytest.approx(expected)
