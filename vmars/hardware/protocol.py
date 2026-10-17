"""Wire formats for the ESP32 motor controller and the JRT laser sensors.

Pure functions only (no I/O) so they can be unit-tested on any machine.
See docs/serial-protocol.md for the full description.
"""

from __future__ import annotations

from typing import NamedTuple

# ─────────────────────────────────────────────────────────────────────────────
# ESP32 (espmotor)  —  ASCII line: "<pitch_steps>,<roll_speed>,<yaw_steps>\n"
# ─────────────────────────────────────────────────────────────────────────────


def format_motor_command(pitch_steps: float, roll_speed: float, yaw_steps: float) -> str:
    """Absolute pitch/yaw targets (steps) and a roll *speed* (steps/s)."""
    return f"{int(pitch_steps)},{roll_speed:.1f},{int(yaw_steps)}\n"


# ─────────────────────────────────────────────────────────────────────────────
# JRT laser distance sensor (binary, header 0xAA)
# ─────────────────────────────────────────────────────────────────────────────
JRT_FRAME_HEADER = 0xAA
JRT_FRAME_BODY_LEN = 12  # bytes following the 0xAA header

CMD_AUTO_BAUD = bytes([0x55])
CMD_READ_VOLTAGE = bytes([0xAA, 0x80, 0x00, 0x06, 0x86])
CMD_LASER_ON = bytes([0xAA, 0x00, 0x01, 0xBE, 0x00, 0x01, 0x00, 0x01, 0xC1])
CMD_LASER_OFF = bytes([0xAA, 0x00, 0x01, 0xBE, 0x00, 0x01, 0x00, 0x00, 0xC0])
CMD_SINGLE_SHOT_AUTO = bytes([0xAA, 0x00, 0x00, 0x20, 0x00, 0x01, 0x00, 0x00, 0x21])


class JrtMeasurement(NamedTuple):
    distance_mm: int
    quality: int


def parse_jrt_frame(body: bytes) -> JrtMeasurement:
    """Decode the 12 bytes that follow the 0xAA header of a measurement reply.

    Bytes 5..8 hold the distance (big endian, mm), bytes 9..10 the signal
    quality (higher is better).
    """
    if len(body) != JRT_FRAME_BODY_LEN:
        raise ValueError(f"expected {JRT_FRAME_BODY_LEN} bytes, got {len(body)}")
    distance = int.from_bytes(body[5:9], "big")
    quality = int.from_bytes(body[9:11], "big")
    return JrtMeasurement(distance, quality)


# ─────────────────────────────────────────────────────────────────────────────
# Sensor register maths
# ─────────────────────────────────────────────────────────────────────────────


def to_int16(high: int, low: int) -> int:
    """Combine two bytes into a signed 16-bit integer."""
    value = (high << 8) | low
    return value - 0x10000 if value >= 0x8000 else value


def sht31_raw_to_celsius(raw: int) -> float:
    return -45.0 + (175.0 * raw / 65535.0)


def wrap_degrees(angle: float) -> float:
    """Map any angle to the range [-180, 180)."""
    return (angle + 180) % 360 - 180
