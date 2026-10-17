"""AUTO mode: tumble, measure thickness, correct the thinnest branch, repeat.

Timeline (``t`` = seconds since START, ``tc`` = seconds into the current cycle)::

    0 ≤ t < 32    pitch (and yaw for T/Y/3D) ramp at 22.5°/s, roll tumbling   "AWAL"
    32 ≤ t < 40   roll + yaw stop, pitch keeps ramping to 900°                "STABIL"
    t ≥ 40        60 s cycles:
        tc < 5      hold base pose, lasers measure (window opens at tc = 1)  "UKUR"
        tc ≥ 5      compute thickness → pick a CorrectionProfile → run it

If the sensors are not all valid when the UKUR window ends, the controller
freezes and asks the UI for a manual correction (``request_correction``).
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Sequence

from vmars import config
from vmars.control.feedback import compute_thickness, decide_condition, has_invalid_point
from vmars.control.motion import (
    FeedbackResult,
    MotionCommand,
    MotionController,
    MotionOffsets,
    ThicknessSensors,
    TickResult,
    near_crucial_angle,
)
from vmars.control.roll import RollPositionTracker
from vmars.control.sequences import CORRECTION_PROFILES

log = logging.getLogger(__name__)


class AutoController(MotionController):
    def __init__(
        self,
        shape: str,
        start_ms: float,
        sensors: ThicknessSensors,
        baseline_mm: Sequence[float],
        offsets: MotionOffsets | None = None,
        perf_counter: Callable[[], float] = time.perf_counter,
    ):
        super().__init__(shape, start_ms, offsets)
        self.sensors = sensors
        self.baseline_mm = tuple(baseline_mm)
        self._perf_counter = perf_counter

        self.yaw_base_deg = 0.0 if shape == "I" else config.AUTO_YAW_BASE_DEG
        self.condition = ""
        self.has_calculated = False
        self.correcting = False
        self._correction_pose = (0.0, 0.0)  # (pitch, yaw) frozen during correction

        self._prereset_done = False
        self._in_measure_window = False
        self._roll = RollPositionTracker(config.STEPS_PER_REV, config.ROLL_SPEED_TUMBLING)
        self._stable_s = 0.0
        self._last_steps = (0, 0)

    # ── called by the UI ─────────────────────────────────────────────────────
    def end_correction(self) -> None:
        self.correcting = False

    # ── main tick ────────────────────────────────────────────────────────────
    def _step(self, now_ms: float, dt_ms: float) -> TickResult:
        if self.correcting:
            return self._correction_tick(dt_ms)

        t_run = (now_ms - self.start_ms) / 1000.0
        self._update_measure_window(t_run)

        if t_run < config.AUTO_INITIAL_PHASE_S:
            pitch, yaw, roll, status = self._initial_phase(t_run)
            return self._finish_tick(pitch, yaw, roll, status, dt_ms)

        t_c = (t_run - config.AUTO_INITIAL_PHASE_S) % config.AUTO_CYCLE_S
        cycle = int((t_run - config.AUTO_INITIAL_PHASE_S) / config.AUTO_CYCLE_S)
        base_pitch = config.AUTO_BASE_PITCH_DEG + cycle * 360.0

        if t_c < config.AUTO_CYCLE_RESET_S and self.has_calculated:
            self.sensors.reset()
            self.has_calculated = False

        if t_c < config.AUTO_MEASURE_WINDOW_S:
            status = f"UKUR ({int(config.AUTO_MEASURE_WINDOW_S - t_c)}s)"
            if self.sensors.all_valid() and not self.has_calculated:
                # Every sensor is done early: jump straight to the end of UKUR.
                self.start_ms -= (config.AUTO_MEASURE_WINDOW_S - t_c) * 1000.0
            return self._finish_tick(base_pitch, self.yaw_base_deg, 0.0, status, dt_ms)

        if not self.has_calculated:
            return self._evaluate_measurement(base_pitch, dt_ms)

        pitch, yaw, roll, status = self._correction_phase(t_c, base_pitch)
        return self._finish_tick(pitch, yaw, roll, status, dt_ms)

    # ── phases ───────────────────────────────────────────────────────────────
    def _update_measure_window(self, t_run: float) -> None:
        in_window = False
        if t_run >= config.AUTO_INITIAL_PHASE_S:
            t_c = (t_run - config.AUTO_INITIAL_PHASE_S) % config.AUTO_CYCLE_S
            # Wait for the roll motor to decelerate and to finish its current
            # revolution before the lasers are allowed to "officially" measure.
            in_window = (
                config.AUTO_MEASURE_SETTLE_S <= t_c < config.AUTO_MEASURE_WINDOW_S
                and not self._roll.finishing
            )
        if in_window != self._in_measure_window:
            self.sensors.set_measurement_window(in_window)
            self._in_measure_window = in_window

    def _initial_phase(self, t_run: float) -> tuple[float, float, float, str]:
        pitch = config.AUTO_TUMBLE_RATE_DEG_S * t_run
        remaining = int(config.AUTO_INITIAL_PHASE_S - t_run)

        if t_run < config.AUTO_ROLL_STOP_S:
            yaw = 0.0 if self.shape == "I" else config.AUTO_TUMBLE_RATE_DEG_S * t_run
            roll, status = config.ROLL_SPEED_TUMBLING, f"AWAL ({remaining}s)"
        else:
            yaw = self.yaw_base_deg
            roll, status = 0.0, f"STABIL ({remaining}s)"

        if t_run >= config.AUTO_SENSOR_PRERESET_S and not self._prereset_done:
            self.sensors.reset()
            self._prereset_done = True
        return pitch, yaw, roll, status

    def _evaluate_measurement(self, base_pitch: float, dt_ms: float) -> TickResult:
        if not self.sensors.all_valid():
            # Timed out: freeze the clock and let the operator nudge the stick.
            self.correcting = True
            self._correction_pose = (base_pitch, self.yaw_base_deg)
            return TickResult(request_correction=True)

        feedback = self._compute_feedback()
        if feedback.valid:
            self.has_calculated = True
        else:
            self.sensors.reset()
            self.start_ms += 5000.0  # rewind 5 s → repeat the UKUR phase

        # Hold the measuring pose on this tick.
        result = self._finish_tick(base_pitch, self.yaw_base_deg, 0.0, None, dt_ms)
        result.feedback = feedback
        return result

    def _correction_phase(self, t_c: float, base_pitch: float) -> tuple[float, float, float, str]:
        profile = CORRECTION_PROFILES.get(self.condition)
        if profile is not None:
            if t_c < profile.travel_until_s:
                return (
                    base_pitch + profile.pitch_offset_deg,
                    self.yaw_base_deg + profile.yaw_offset_deg,
                    config.ROLL_SPEED_TUMBLING,
                    profile.travel_label,
                )
            if t_c < profile.hold_until_s:
                return (
                    base_pitch + profile.pitch_offset_deg,
                    self.yaw_base_deg + profile.yaw_offset_deg,
                    profile.hold_roll_speed,
                    f"{profile.hold_label} ({int(profile.hold_until_s - t_c)}s)",
                )
        # Done (or no correction needed): one more revolution and keep tumbling.
        return base_pitch + 360.0, self.yaw_base_deg, config.ROLL_SPEED_TUMBLING, "LANJUT"

    def _correction_tick(self, dt_ms: float) -> TickResult:
        self.start_ms += dt_ms  # process clock stays frozen
        pitch, yaw = self._correction_pose
        command = MotionCommand.from_degrees(
            pitch + self.offsets.pitch_deg,
            0.0 + self.offsets.roll_speed,
            yaw + self.offsets.yaw_deg,
        )
        return TickResult(command=command)

    # ── feedback ─────────────────────────────────────────────────────────────
    def _compute_feedback(self) -> FeedbackResult:
        distances = self.sensors.best_distances()
        thickness = compute_thickness(self.baseline_mm, distances)
        log.info("=== FEEDBACK (%s-shape) ===", self.shape)
        log.info("RAW DISTANCE -> S1: %s mm | S2: %s mm | S3: %s mm", *distances)
        log.info("THICKNESS    -> S1: %s mm | S2: %s mm | S3: %s mm", *thickness)

        if has_invalid_point(thickness, self.sensors.connected()):
            log.warning("Invalid measurement (0 mm thickness). Repeating measurement...")
            return FeedbackResult(distances, thickness, valid=False)

        condition, reason = decide_condition(self.shape, thickness)
        self.condition = condition
        log.info("RESULT: %s (%s)", reason, condition or "no correction")

        response_ms = (self._perf_counter() - self.sensors.last_valid_finish_time()) * 1000.0
        if response_ms < 0:
            response_ms = 1.0
        return FeedbackResult(distances, thickness, True, condition, reason, response_ms)

    # ── common tail of every motion tick ─────────────────────────────────────
    def _finish_tick(
        self, pitch: float, yaw: float, roll: float, status: str | None, dt_ms: float
    ) -> TickResult:
        pitch += self.offsets.pitch_deg
        yaw += self.offsets.yaw_deg
        roll += self.offsets.roll_speed

        command = MotionCommand.from_degrees(pitch, roll, yaw)

        # "Stable" = same pitch/yaw target and roll stopped for a while.
        steps = (command.pitch_steps, command.yaw_steps)
        if steps == self._last_steps and roll == 0.0:
            self._stable_s += config.CONTROL_PERIOD_MS / 1000.0
        else:
            self._stable_s = 0.0
        self._last_steps = steps

        # Never stop the roll mid-revolution: finish to the next full turn.
        roll = self._roll.update(roll, dt_ms / 1000.0)
        command = MotionCommand(command.pitch_steps, roll, command.yaw_steps)

        low, high = config.AUTO_IMU_STABLE_WINDOW_S
        imu_active = (
            near_crucial_angle(self.shape, pitch, config.AUTO_IMU_ANGLE_TOLERANCE_DEG)
            and low < self._stable_s < high
        )
        return TickResult(command=command, status=status, imu_active=imu_active)

