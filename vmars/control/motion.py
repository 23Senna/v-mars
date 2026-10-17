"""Shared types for the AUTO and MANUAL motion controllers.

The controllers are plain Python objects: they receive the current time and
return what the motors should do. They know nothing about Qt, serial ports or
the database, which makes the whole motion sequence testable in simulation
(see ``tests/``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from vmars import config


@dataclass
class MotionOffsets:
    """Operator nudges added on top of the planned trajectory.

    ``pitch_deg``/``yaw_deg`` are permanent offsets; ``roll_speed`` is a
    temporary extra roll speed (steps/s) that the UI resets after a nudge.
    """

    pitch_deg: float = 0.0
    yaw_deg: float = 0.0
    roll_speed: float = 0.0

    def clear(self) -> None:
        self.pitch_deg = self.yaw_deg = self.roll_speed = 0.0


@dataclass(frozen=True)
class MotionCommand:
    pitch_steps: int
    roll_speed: float
    yaw_steps: int

    @classmethod
    def from_degrees(cls, pitch_deg: float, roll_speed: float, yaw_deg: float) -> "MotionCommand":
        return cls(
            int(pitch_deg * config.STEPS_PER_DEGREE),
            roll_speed,
            int(yaw_deg * config.STEPS_PER_DEGREE),
        )

    def stopped(self) -> "MotionCommand":
        """Same pitch/yaw targets with the roll motor stopped."""
        return MotionCommand(self.pitch_steps, 0.0, self.yaw_steps)


@dataclass(frozen=True)
class FeedbackResult:
    distances_mm: tuple[float, float, float]
    thickness_mm: tuple[float, float, float]
    valid: bool
    condition: str = ""
    reason: str = ""
    response_time_ms: float = 0.0


@dataclass
class TickResult:
    """What one control tick decided.

    ``None`` fields mean "leave unchanged" (e.g. the status label).
    """

    command: Optional[MotionCommand] = None
    status: Optional[str] = None
    imu_active: Optional[bool] = None
    request_correction: bool = False
    feedback: Optional[FeedbackResult] = None


class ThicknessSensors(Protocol):
    """What the AUTO controller needs from the laser sensors."""

    def set_measurement_window(self, active: bool) -> None: ...
    def reset(self) -> None: ...
    def all_valid(self) -> bool: ...
    def best_distances(self) -> tuple[float, float, float]: ...
    def connected(self) -> tuple[bool, bool, bool]: ...
    def last_valid_finish_time(self) -> float: ...


def near_crucial_angle(shape: str, pitch_deg: float, tolerance_deg: float) -> bool:
    """Is the pitch target within ``tolerance_deg`` of one of the shape's
    crucial angles (where the IMU should be sampled)?"""
    rel = pitch_deg % 360.0
    angles = config.CRUCIAL_ANGLES.get(shape, config.CRUCIAL_ANGLES["I"])
    return any(min((rel - a) % 360, (a - rel) % 360) <= tolerance_deg for a in angles)


class MotionController:
    """Base class: time bookkeeping and pause handling."""

    def __init__(self, shape: str, start_ms: float, offsets: Optional[MotionOffsets] = None):
        self.shape = shape
        self.start_ms = start_ms
        self.offsets = offsets if offsets is not None else MotionOffsets()
        self.last_update_ms = start_ms
        self.last_command = MotionCommand(0, 0.0, 0)

    def update(self, now_ms: float, paused: bool = False) -> TickResult:
        dt_ms = now_ms - self.last_update_ms
        self.last_update_ms = now_ms

        if paused:
            # Freeze the process clock and keep the motors where they are.
            self.start_ms += dt_ms
            return TickResult(command=self.last_command.stopped())

        result = self._step(now_ms, dt_ms)
        if result.command is not None:
            self.last_command = result.command
        return result

    def stop_command(self) -> MotionCommand:
        return self.last_command.stopped()

    def _step(self, now_ms: float, dt_ms: float) -> TickResult:  # pragma: no cover
        raise NotImplementedError
