"""MANUAL mode: continuous tumbling plus operator-selected holds.

The platform tumbles at 45°/s in an 8 s cycle. When the operator picks a
preset, the controller waits for the preset's point in the cycle, then holds
that pitch/yaw for 30 s (optionally rolling), and resumes tumbling.
Laser sensors are not used in this mode.
"""

from __future__ import annotations

import math

from vmars import config
from vmars.control.motion import (
    MotionCommand,
    MotionController,
    MotionOffsets,
    TickResult,
    near_crucial_angle,
)
from vmars.control.sequences import ManualPreset


class ManualController(MotionController):
    def __init__(self, shape: str, start_ms: float, offsets: MotionOffsets | None = None):
        super().__init__(shape, start_ms, offsets)
        self.preset: ManualPreset | None = None
        self.waiting = False   # preset chosen, waiting for its moment in the cycle
        self.staying = False   # holding the preset pose
        self._stay_left_s = 0.0
        self._held_s = 0.0     # total hold time, excluded from the tumbling clock
        self._locked_pose = (0.0, 0.0)

    # ── called by the UI ─────────────────────────────────────────────────────
    def select_preset(self, preset: ManualPreset) -> None:
        self.preset = preset
        self.waiting = True
        self.staying = False

    def resume_tumbling(self) -> None:
        self.waiting = False
        self.staying = False

    # ── main tick ────────────────────────────────────────────────────────────
    def _step(self, now_ms: float, dt_ms: float) -> TickResult:
        dt = dt_ms / 1000.0
        cycle = config.MANUAL_CYCLE_S
        rate = config.MANUAL_TUMBLE_RATE_DEG_S

        if self.staying:
            self._stay_left_s -= dt
            self._held_s += dt
            status = f"TAHAN ({int(self._stay_left_s)}s)"
            pitch, yaw = self._locked_pose
            roll = self.preset.roll_speed
            if self._stay_left_s <= 0:
                self.staying = self.waiting = False
                status = "NORMAL"
                roll = config.ROLL_SPEED_TUMBLING
        else:
            t_eff = (now_ms - self.start_ms) / 1000.0 - self._held_s
            pitch = rate * t_eff
            yaw = 0.0 if self.shape == "I" else rate * t_eff
            roll = config.ROLL_SPEED_TUMBLING
            status = "NORMAL"

            if self.waiting:
                status = f"TUNGGU {self.preset.cycle_time_s}s"
                self._maybe_start_stay(t_eff, dt, cycle)

        pitch += self.offsets.pitch_deg
        yaw += self.offsets.yaw_deg
        roll += self.offsets.roll_speed

        return TickResult(
            command=MotionCommand.from_degrees(pitch, roll, yaw),
            status=status,
            imu_active=near_crucial_angle(self.shape, pitch, config.MANUAL_IMU_ANGLE_TOLERANCE_DEG),
        )

    def _maybe_start_stay(self, t_eff: float, dt: float, cycle: float) -> None:
        # Preset times are defined for the original 16 s cycle; the cycle now
        # runs twice as fast, so the target point is halved as well.
        target_in_cycle = self.preset.cycle_time_s / 2.0
        target = math.floor(t_eff / cycle) * cycle + target_in_cycle
        if target < t_eff:
            target += cycle

        if target - t_eff <= dt * 1.5:
            self.staying = True
            self._stay_left_s = config.MANUAL_STAY_DURATION_S
            # Lock absolute angles in the *current* revolution so the motors
            # never unwind back to the preset angle.
            revolutions = math.floor(target / cycle)
            pitch = revolutions * 360.0 + self.preset.pitch_deg
            yaw = 0.0 if self.shape == "I" else revolutions * 360.0 + self.preset.yaw_deg
            self._locked_pose = (pitch, yaw)
